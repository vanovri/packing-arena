"""Deterministic bin packing using best fit, subset sums, and bin completion.

The constructive portfolio preserves an immediately usable packing. A bounded
bin-completion search then tries smaller bin counts. Integer subset-sum tables
enumerate complete bin patterns, with equal weights handled as counts. Search
limits are operation counts, so the returned packing is deterministic.
"""

def solve(items, capacity=100):
    """Return bins containing original item indices; never mutate ``items``."""
    n = len(items)
    if not n:
        return []
    order = sorted(range(n), key=lambda i: (-items[i], i))
    total = sum(items)
    lower = (total + capacity - 1) // capacity

    # When three items cannot share a bin, sorted pairing is optimal.
    if 3 * min(items) > capacity:
        result = []
        lo, hi = 0, n - 1
        while lo <= hi:
            current = [order[lo]]
            if lo < hi and items[order[lo]] + items[order[hi]] <= capacity:
                current.append(order[hi])
                hi -= 1
            lo += 1
            result.append(current)
        return result

    def best_fit(sequence):
        bins, free = [], []
        for i in sequence:
            w = items[i]
            position = -1
            best_space = capacity + 1
            for j, space in enumerate(free):
                if w <= space < best_space:
                    best_space = space
                    position = j
            if position < 0:
                bins.append([i])
                free.append(capacity - w)
            else:
                bins[position].append(i)
                free[position] -= w
        return bins

    best = best_fit(order)
    if len(best) == lower:
        return best

    # The L2 bound excludes tiny items that cannot enter the largest bins.
    for threshold in range(1, capacity // 2 + 1):
        large = medium = medium_sum = small_sum = 0
        for w in items:
            if w > capacity - threshold:
                large += 1
            elif 2 * w > capacity:
                medium += 1
                medium_sum += w
            elif w >= threshold:
                small_sum += w
        uncovered = max(0, small_sum - (medium * capacity - medium_sum))
        bound = large + medium + (uncovered + capacity - 1) // capacity
        if bound > lower:
            lower = bound
    if len(best) == lower:
        return best

    def subset_pack(mode):
        remaining = order[:]
        result = []
        while remaining:
            anchor = remaining.pop(0)
            room = capacity - items[anchor]
            if mode == 1:
                sequence = remaining[::-1]
            elif mode == 2:
                sequence = remaining[::2] + remaining[1::2]
            else:
                sequence = remaining
            reachable = 1
            history = []
            mask = (1 << (room + 1)) - 1
            for i in sequence:
                history.append(reachable)
                reachable = (reachable | (reachable << items[i])) & mask
            target = reachable.bit_length() - 1
            chosen = {anchor}
            current = [anchor]
            for pos in range(len(sequence) - 1, -1, -1):
                if not (history[pos] >> target) & 1:
                    i = sequence[pos]
                    chosen.add(i)
                    current.append(i)
                    target -= items[i]
            remaining = [i for i in remaining if i not in chosen]
            result.append(current)
        return result

    for mode in range(3):
        candidate = subset_pack(mode)
        if len(candidate) < len(best):
            best = candidate
            if len(best) == lower:
                return best

    # Work counts bound even pathological instances without clock dependence.
    weights = sorted(set(items), reverse=True)
    counts = [0] * len(weights)
    location = {w: j for j, w in enumerate(weights)}
    for w in items:
        counts[location[w]] += 1
    original_counts = counts[:]
    work = 0
    limit = 60000
    exhausted = False
    failed = set()

    def complete(bins_left, remaining_total, remaining_count, depth=0):
        nonlocal work, exhausted
        work += 1
        if work >= limit or depth >= 600:
            exhausted = True
            return None
        if not remaining_count:
            return []
        if remaining_total <= capacity:
            return [[(j, count) for j, count in enumerate(counts) if count]]
        if bins_left <= 1:
            return None
        if remaining_count <= bins_left:
            return [[(j, 1)] for j, count in enumerate(counts) for _ in range(count)]
        state = (bins_left, tuple(counts))
        if state in failed:
            return None
        first = next(j for j, count in enumerate(counts) if count)
        if sum(counts[j] for j in range(first, len(weights)) if 2 * weights[j] > capacity) > bins_left:
            failed.add(state)
            return None
        counts[first] -= 1
        anchor = weights[first]
        room = capacity - anchor
        active = [j for j in range(first, len(weights)) if counts[j] and weights[j] <= room]
        suffix = [1] * (len(active) + 1)
        mask = (1 << (room + 1)) - 1
        for p in range(len(active) - 1, -1, -1):
            j = active[p]
            reachable = suffix[p + 1]
            shifted = reachable
            for _ in range(min(counts[j], room // weights[j])):
                shifted <<= weights[j]
                reachable |= shifted
            suffix[p] = reachable & mask
        pattern = [(first, 1)]

        def choose(p, target, packed, selected, depth):
            nonlocal work, exhausted
            work += 1
            if work >= limit or depth >= 600:
                exhausted = True
                return None
            if target == 0:
                # Every completed bin may be assumed maximal.
                slack = capacity - anchor - packed
                if slack and any(count and w <= slack for w, count in zip(weights, counts)):
                    return None
                tail = complete(bins_left - 1, remaining_total - anchor - packed,
                                remaining_count - 1 - selected, depth + 1)
                if tail is not None:
                    return [pattern[:]] + tail
                return None
            if p == len(active) or not (suffix[p] >> target) & 1:
                return None
            j = active[p]
            w = weights[j]
            maximum = min(counts[j], target // w)
            for take in range(maximum, -1, -1):
                rest = target - take * w
                if not (suffix[p + 1] >> rest) & 1:
                    continue
                if take:
                    counts[j] -= take
                    pattern.append((j, take))
                result = choose(p + 1, rest, packed + take * w, selected + take, depth + 1)
                if take:
                    pattern.pop()
                    counts[j] += take
                if result is not None or exhausted:
                    return result
            return None

        # Bin slack cannot exceed the unused space across all remaining bins.
        minimum = max(0, remaining_total - (bins_left - 1) * capacity - anchor)
        result = None
        for target in range(room, minimum - 1, -1):
            if (suffix[0] >> target) & 1:
                result = choose(0, target, 0, 0, depth + 1)
                if result is not None or exhausted:
                    break
        counts[first] += 1
        if result is None and not exhausted:
            failed.add(state)
        return result

    for target_bins in range(len(best) - 1, lower - 1, -1):
        counts[:] = original_counts
        patterns = complete(target_bins, total, n)
        if patterns is None:
            break
        by_weight = [[] for _ in weights]
        for i in range(n - 1, -1, -1):
            by_weight[location[items[i]]].append(i)
        best = []
        for pattern in patterns:
            current = []
            for j, count in pattern:
                for _ in range(count):
                    current.append(by_weight[j].pop())
            best.append(current)
    return best


if __name__ == '__main__':
    import random
    import time

    def check(values, capacity=100):
        result = solve(values, capacity)
        assert sorted(i for group in result for i in group) == list(range(len(values)))
        assert all(group and sum(values[i] for i in group) <= capacity for group in result)
        assert result == solve(values, capacity)
        return len(result)

    assert check([]) == 0
    assert check([100, 1, 99, 50, 50]) == 3
    assert check([6, 5, 3, 2, 2, 2], 10) == 2
    assert check([51] * 180) == 180
    assert check([1] * 180) == 2
    rng = random.Random(712093)
    started = time.perf_counter()
    for _ in range(80):
        check([rng.randint(1, 100) for _ in range(rng.randrange(181))])
    print('self-test passed: 85 cases, deterministic, %.3f s' % (time.perf_counter() - started))
