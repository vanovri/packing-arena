"""Deterministic bin packing with greedy, subset-sum, and bounded exact search.

Best/first fit decreasing provide an immediate feasible incumbent. Anchored
subset-sum completion tries several deterministic tie orders. Volume, L2, and
cardinality bounds stop work when optimality is proved. Frequency-based bin
completion and symmetry-pruned assignment search then attempt fewer bins under
fixed operation budgets. All outputs contain original indices; input is intact.
"""

from bisect import bisect_left
from random import Random


def solve(items, capacity=100):
    """Return a feasible list of bins containing original item indices."""
    n = len(items)
    if not n:
        return []
    if capacity <= 0 or any(w <= 0 or w > capacity for w in items):
        raise ValueError("Every weight must be positive and at most capacity")
    order = sorted(range(n), key=lambda i: (-items[i], i))
    if n < 3 or sum(items[i] for i in order[-3:]) > capacity:
        bins = []
        left, right = 0, n - 1
        while left <= right:
            current = [order[left]]
            if left < right and items[order[left]] + items[order[right]] <= capacity:
                current.append(order[right])
                right -= 1
            left += 1
            bins.append(current)
        return bins
    total = sum(items)
    lower = (total + capacity - 1) // capacity
    frequency = [0] * (capacity + 1)
    for w in items:
        frequency[w] += 1
    count = 0
    for threshold in range(capacity, 0, -1):
        count += frequency[threshold]
        slots = capacity // threshold
        lower = max(lower, (count + slots - 1) // slots)
    half = capacity // 2
    large = [items[i] for i in order if items[i] > half]
    lower = max(lower, len(large))
    # L2: items above C-k cannot share with items of weight at least k.
    for k in range(1, half + 1):
        available = sum(capacity - w for w in large if w <= capacity - k)
        small = sum(w for w in items if k <= w <= half)
        lower = max(lower, len(large) + max(0, (small - available + capacity - 1) // capacity))

    def greedy(first=False):
        bins, rooms = [], []
        for i in order:
            w = items[i]
            chosen = -1
            best_room = capacity + 1
            for j, room in enumerate(rooms):
                if w <= room < best_room:
                    chosen, best_room = j, room
                    if first or room == w:
                        break
            if chosen < 0:
                bins.append([i])
                rooms.append(capacity - w)
            else:
                bins[chosen].append(i)
                rooms[chosen] -= w
        return bins

    best = greedy()
    if len(best) == lower:
        return best
    candidate = greedy(True)
    if len(candidate) < len(best):
        best = candidate
    if len(best) == lower:
        return best

    def completion(sequence):
        remaining = set(order)
        bins = []
        for anchor in order:
            if anchor not in remaining:
                continue
            remaining.remove(anchor)
            room = capacity - items[anchor]
            chosen = [anchor]
            if room:
                reachable = 1
                history = []
                mask = (1 << (room + 1)) - 1
                for i in sequence:
                    if i in remaining and items[i] <= room:
                        history.append((i, reachable))
                        reachable |= (reachable << items[i]) & mask
                        if reachable & (1 << room):
                            break
                fill = reachable.bit_length() - 1
                for i, before in reversed(history):
                    if not (before >> fill) & 1:
                        chosen.append(i)
                        remaining.remove(i)
                        fill -= items[i]
            bins.append(chosen)
        return bins

    rng = Random(0xC0BA17)
    for mode in range(8):
        if mode == 0:
            sequence = order
        elif mode == 1:
            sequence = list(reversed(order))
        else:
            sequence = order.copy()
            rng.shuffle(sequence)
        candidate = completion(sequence)
        if len(candidate) < len(best):
            best = candidate
            if len(best) == lower:
                return best

    # Search whole bin patterns first: equal weights have no index symmetry.
    kinds = sorted(set(items), reverse=True)
    counts = [frequency[w] for w in kinds]
    pattern_budget = 18000
    stopped = False
    failed_patterns = set()

    def pattern_search(bins_left, remaining_total, remaining_count):
        nonlocal pattern_budget, stopped
        pattern_budget -= 1
        if pattern_budget < 0:
            stopped = True
            return None
        if remaining_total <= capacity:
            return [[(j, c) for j, c in enumerate(counts) if c]] if remaining_count else []
        if bins_left <= 1:
            return None
        if remaining_count <= bins_left:
            return [[(j, 1)] for j, c in enumerate(counts) for _ in range(c)]
        first = next(j for j, c in enumerate(counts) if c)
        smallest = next(kinds[j] for j in range(len(kinds) - 1, first - 1, -1) if counts[j])
        if remaining_count > bins_left * (capacity // smallest):
            return None
        if sum(c for w, c in zip(kinds, counts) if 2 * w > capacity) > bins_left:
            return None
        state = (bins_left, tuple(counts))
        if state in failed_patterns:
            return None
        counts[first] -= 1
        room = capacity - kinds[first]
        active = [j for j in range(first, len(kinds)) if counts[j] and kinds[j] <= room]
        mask = (1 << (room + 1)) - 1
        suffix = [1] * (len(active) + 1)
        for p in range(len(active) - 1, -1, -1):
            j = active[p]
            reachable = suffix[p + 1]
            available = min(counts[j], room // kinds[j])
            block = 1
            while available:
                take = min(block, available)
                reachable |= reachable << (take * kinds[j])
                reachable &= mask
                available -= take
                block *= 2
                pattern_budget -= 1
            suffix[p] = reachable
        pattern = []

        def enumerate_patterns(p, target):
            nonlocal pattern_budget, stopped
            pattern_budget -= 1
            if pattern_budget < 0:
                stopped = True
                return
            if target == 0:
                yield tuple(pattern)
                return
            if p == len(active) or not (suffix[p] >> target) & 1:
                return
            j = active[p]
            w = kinds[j]
            for take in range(min(counts[j], target // w), -1, -1):
                rest = target - take * w
                if not (suffix[p + 1] >> rest) & 1:
                    continue
                if take:
                    pattern.append((j, take))
                yield from enumerate_patterns(p + 1, rest)
                if take:
                    pattern.pop()
                if stopped:
                    return

        minimum = max(0, remaining_total - (bins_left - 1) * capacity - kinds[first])
        answer = None
        for fill in range(room, minimum - 1, -1):
            if not (suffix[0] >> fill) & 1:
                continue
            for chosen in enumerate_patterns(0, fill):
                selected = 0
                for j, c in chosen:
                    counts[j] -= c
                    selected += c
                tail = pattern_search(bins_left - 1, remaining_total - kinds[first] - fill,
                                      remaining_count - 1 - selected)
                for j, c in chosen:
                    counts[j] += c
                if tail is not None:
                    answer = [[(first, 1)] + list(chosen)] + tail
                    break
                if stopped:
                    break
            if answer is not None or stopped:
                break
        counts[first] += 1
        if answer is None and not stopped:
            failed_patterns.add(state)
        return answer

    while len(best) > lower and pattern_budget > 0:
        patterns = pattern_search(len(best) - 1, total, n)
        if patterns is None:
            if not stopped:
                return best
            break
        by_weight = {w: [] for w in kinds}
        for i in reversed(range(n)):
            by_weight[items[i]].append(i)
        best = [[by_weight[kinds[j]].pop() for j, c in group for _ in range(c)]
                for group in patterns]
        if len(best) == lower:
            return best

    weights = [items[i] for i in order]
    # shortcut: fixed search budget may leave a feasible nonoptimal incumbent.
    budget = 30000

    def exact(count):
        nonlocal budget
        rooms = [capacity] * count
        bins = [[] for _ in range(count)]
        failed = set()

        def place(pos):
            nonlocal budget
            if pos == n:
                return True
            budget -= 1
            if budget < 0:
                return False
            state = tuple(rooms)
            if state in failed:
                return False
            w = weights[pos]
            start = bisect_left(rooms, w)
            previous = -1
            for j in range(start, count):
                room = rooms[j]
                if room == previous:
                    continue
                previous = room
                new_room = room - w
                insert = bisect_left(rooms, new_room, 0, j)
                saved = bins.pop(j)
                rooms.pop(j)
                saved.append(order[pos])
                bins.insert(insert, saved)
                rooms.insert(insert, new_room)
                if place(pos + 1):
                    return True
                rooms.pop(insert)
                bins.pop(insert)
                saved.pop()
                rooms.insert(j, room)
                bins.insert(j, saved)
                if budget < 0 or room == w or room == capacity:
                    break
            if budget >= 0:
                failed.add(state)
            return False

        return [b.copy() for b in bins if b] if place(0) else None

    while len(best) > lower and budget > 0:
        candidate = exact(len(best) - 1)
        if candidate is None:
            break
        best = candidate
    return best


if __name__ == "__main__":
    from time import perf_counter

    def check(values, expected=None, capacity=100):
        packed = solve(values, capacity)
        assert sorted(i for b in packed for i in b) == list(range(len(values)))
        assert all(b and sum(values[i] for i in b) <= capacity for b in packed)
        if expected is not None:
            assert len(packed) == expected, (values, packed)

    check([], 0)
    check([100], 1)
    check([51, 49, 50, 50], 2)
    check([60, 60, 40, 40, 20, 20, 20, 20], 3)
    check([1] * 180, 2)
    check([51] * 180, 180)
    check([26] * 180, 60)
    check([33] + [40] * 89 + [61] * 90, 135)
    check([6, 4, 5, 5], 2, 10)
    triples = Random(8873)
    values = []
    for _ in range(60):
        a = triples.randint(25, 49)
        b = triples.randint(25, 75 - a)
        values.extend([a, b, 100 - a - b])
    triples.shuffle(values)
    check(values, 60)
    generator = Random(20261024)
    timings = []
    for _ in range(120):
        values = [generator.randint(1, 100) for _ in range(generator.randint(0, 180))]
        start = perf_counter()
        check(values)
        timings.append(perf_counter() - start)
    print("130 self-tests passed; max runtime %.6f s" % max(timings))
