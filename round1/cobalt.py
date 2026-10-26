"""Deterministic bin packing with greedy, subset-sum, and bounded exact search.

Best/first fit decreasing provide an immediate feasible incumbent. Anchored
subset-sum completion tries several deterministic tie orders. A volume and L2
lower bound stops work when optimality is proved. Otherwise a symmetry-pruned
assignment search attempts fewer bins under a fixed node budget. All outputs
contain original indices; the input is never modified.
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
    total = sum(items)
    lower = (total + capacity - 1) // capacity
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

    weights = [items[i] for i in order]
    # shortcut: fixed search budget may leave a feasible nonoptimal incumbent.
    budget = 50000

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
    check([6, 4, 5, 5], 2, 10)
    generator = Random(20261024)
    timings = []
    for _ in range(120):
        values = [generator.randint(1, 100) for _ in range(generator.randint(0, 180))]
        start = perf_counter()
        check(values)
        timings.append(perf_counter() - start)
    print("127 self-tests passed; max runtime %.6f s" % max(timings))
