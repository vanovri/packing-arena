"""Deterministic bin packing with index-preserving output.

Combine best-fit decreasing, several bitset subset-sum completions, and exact
three-bin-to-two-bin and bounded four-bin-to-three-bin repacking. A bounded
branch-and-bound search attempts further one-bin improvements. A valid incumbent is always available, and all
search budgets count operations rather than consulting a clock.
"""


def _lower_bound(weights, capacity):
    bound = (sum(weights) + capacity - 1) // capacity
    counts = [0] * (capacity + 1)
    for weight in weights:
        counts[weight] += 1
    at_least = 0
    for threshold in range(capacity, 0, -1):
        at_least += counts[threshold]
        per_bin = capacity // threshold
        bound = max(bound, (at_least + per_bin - 1) // per_bin)
    half = capacity // 2
    for alpha in range(1, half + 1):
        huge = medium = medium_sum = small_sum = 0
        for w in weights:
            if w > capacity - alpha:
                huge += 1
            elif w > half:
                medium += 1
                medium_sum += w
            elif w >= alpha:
                small_sum += w
        excess = small_sum - (medium * capacity - medium_sum)
        bound = max(bound, huge + medium + max(0, (excess + capacity - 1) // capacity))
    return bound


def _best_fit(order, weights, capacity):
    bins, remaining = [], []
    for index in order:
        weight = weights[index]
        target, slack = -1, capacity + 1
        for b, free in enumerate(remaining):
            if weight <= free < slack:
                target, slack = b, free
        if target < 0:
            bins.append([index])
            remaining.append(capacity - weight)
        else:
            bins[target].append(index)
            remaining[target] -= weight
    return bins


def _subset(indices, weights, limit):
    """Return a maximum-sum subset, reconstructing only newly reached sums."""
    reachable, mask = 1, (1 << (limit + 1)) - 1
    parent_item = [-1] * (limit + 1)
    parent_sum = [0] * (limit + 1)
    for index in indices:
        weight = weights[index]
        new = (reachable << weight) & mask & ~reachable
        reachable |= new
        while new:
            bit = new & -new
            value = bit.bit_length() - 1
            parent_item[value] = index
            parent_sum[value] = value - weight
            new ^= bit
        if reachable >> limit:
            break
    value = reachable.bit_length() - 1
    selected = []
    while value:
        selected.append(parent_item[value])
        value = parent_sum[value]
    return selected


def _completion(order, weights, capacity, variant):
    pending, bins = order[:], []
    state = 104729 * (variant + 1)
    while pending:
        anchor = pending[0]
        candidates = pending[1:]
        if variant == 1:
            candidates.reverse()
        elif variant == 2:
            candidates = candidates[::2] + candidates[1::2][::-1]
        elif variant >= 3:
            # Local integer generator keeps behavior independent of global random state.
            for j in range(len(candidates) - 1, 0, -1):
                state = (1664525 * state + 1013904223) & 0xffffffff
                k = state % (j + 1)
                candidates[j], candidates[k] = candidates[k], candidates[j]
        chosen = [anchor] + _subset(candidates, weights, capacity - weights[anchor])
        selected = set(chosen)
        pending = [i for i in pending if i not in selected]
        bins.append(chosen)
    return bins


def _compact(bins, weights, capacity):
    """Exactly repack small groups, retaining original item indices."""
    bins = [b[:] for b in bins]
    mask = (1 << (capacity + 1)) - 1
    tests = 0
    while len(bins) > 1:
        bins.sort(key=lambda b: (sum(weights[i] for i in b), b))
        loads = [sum(weights[i] for i in b) for b in bins]
        if loads[0] + loads[1] <= capacity:
            bins[0].extend(bins.pop(1))
            continue
        improved = False
        for a in range(len(bins) - 2):
            if loads[a] + loads[a + 1] + loads[a + 2] > 2 * capacity:
                break
            for b in range(a + 1, len(bins) - 1):
                if loads[a] + loads[b] + loads[b + 1] > 2 * capacity:
                    break
                for c in range(b + 1, len(bins)):
                    total = loads[a] + loads[b] + loads[c]
                    if total > 2 * capacity:
                        break
                    tests += 1
                    if tests > 3500:
                        return bins
                    indices = bins[a] + bins[b] + bins[c]
                    reachable = 1
                    for i in indices:
                        reachable = (reachable | (reachable << weights[i])) & mask
                    if reachable.bit_length() - 1 < total - capacity:
                        continue
                    chosen = _subset(indices, weights, capacity)
                    selected = set(chosen)
                    other = [i for i in indices if i not in selected]
                    for target in (c, b, a):
                        bins.pop(target)
                    bins.extend((chosen, other))
                    improved = True
                    break
                if improved:
                    break
            if improved:
                break
        if not improved:
            break
    return bins


def _search(order, weights, capacity, count, budget):
    """Try a bin count using capacity buckets and return nodes consumed."""
    n = len(order)
    values = [weights[i] for i in order]
    buckets = [[] for _ in range(capacity + 1)]
    buckets[capacity] = list(range(count))
    counts = [0] * (capacity + 1)
    counts[capacity] = count
    occupied = 1 << capacity if count else 0
    bins = [[] for _ in range(count)]
    failed = set()
    nodes = 0
    aborted = False

    def visit(pos):
        nonlocal nodes, aborted, occupied
        nodes += 1
        if nodes > budget:
            aborted = True
            return False
        if pos == n:
            return True
        weight = values[pos]
        options = (occupied >> weight) << weight
        if not options:
            return False
        # There are at most 180 bins, so each histogram entry fits one byte.
        key = (pos, bytes(counts))
        if key in failed:
            return False
        while options:
            bit = options & -options
            options ^= bit
            free = bit.bit_length() - 1
            saved_mask = occupied
            target = buckets[free].pop()
            counts[free] -= 1
            if not counts[free]:
                occupied ^= bit
            new_free = free - weight
            buckets[new_free].append(target)
            counts[new_free] += 1
            occupied |= 1 << new_free
            bins[target].append(order[pos])
            if visit(pos + 1):
                return True
            bins[target].pop()
            buckets[new_free].pop()
            counts[new_free] -= 1
            buckets[free].append(target)
            counts[free] += 1
            occupied = saved_mask
            if aborted:
                return False
            # Exact fill dominates other placements by exchanging later items.
            if free == weight or free == capacity:
                break
        if len(failed) < 12000:
            failed.add(key)
        return False

    found = visit(0)
    return (bins if found else None), min(nodes, budget)


def _compact_four(bins, weights, capacity):
    """Spend a small shared node budget repacking four light bins into three."""
    from itertools import combinations

    bins = [b[:] for b in bins]
    budget = 2500
    while len(bins) >= 4 and budget > 0:
        bins.sort(key=lambda b: (sum(weights[i] for i in b), b))
        loads = [sum(weights[i] for i in b) for b in bins]
        improved = False
        for group in combinations(range(min(14, len(bins))), 4):
            if sum(loads[b] for b in group) > 3 * capacity:
                continue
            indices = [i for b in group for i in bins[b]]
            indices.sort(key=lambda i: (-weights[i], i))
            candidate, used = _search(indices, weights, capacity, 3, min(300, budget))
            budget -= used
            if candidate is not None:
                for b in reversed(group):
                    bins.pop(b)
                bins.extend(candidate)
                improved = True
                break
            if budget <= 0:
                break
        if not improved:
            break
    return bins


def solve(items, capacity=100):
    """Pack every input index exactly once; integer weights must fit capacity."""
    if not items:
        return []
    order = sorted(range(len(items)), key=lambda i: (-items[i], i))
    best = _best_fit(order, items, capacity)
    volume = (sum(items) + capacity - 1) // capacity
    if len(best) == volume:
        return best
    lower = _lower_bound(items, capacity)
    if len(best) == lower:
        return best
    best = _compact(best, items, capacity)
    if len(best) == lower:
        return best
    for variant in range(9):
        candidate = _completion(order, items, capacity, variant)
        if len(candidate) <= len(best):
            candidate = _compact(candidate, items, capacity)
            if len(candidate) < len(best):
                best = candidate
                if len(best) == lower:
                    return best
    best = _compact_four(best, items, capacity)
    # shortcut: bounded search can miss an optimum; increase only with a larger budget.
    budget = 24000
    while len(best) > lower and budget > 0:
        candidate, used = _search(order, items, capacity, len(best) - 1, budget)
        budget -= used
        if candidate is None:
            break
        best = candidate
    return best


if __name__ == '__main__':
    import random
    import time

    cases = [[], [100], [50] * 180, [33] * 120, [51] * 90 + [49] * 90,
             [60, 60, 40, 40], [44, 24, 24, 22, 21, 17, 8, 8, 6, 6]]
    cases.extend([[w] * 180 for w in (21, 26, 34, 41)])
    for w in (21, 26, 34, 41):
        expected = (180 + 100 // w - 1) // (100 // w)
        assert _lower_bound([w] * 180, 100) == expected
        assert len(solve([w] * 180)) == expected
    four_weights = [40, 30] * 4
    four_result = _compact_four([[2*j, 2*j+1] for j in range(4)], four_weights, 100)
    assert len(four_result) == 3
    assert sorted(i for b in four_result for i in b) == list(range(8))
    assert all(sum(four_weights[i] for i in b) <= 100 for b in four_result)
    rng = random.Random(20261024)
    cases.extend([rng.randint(1, 100) for _ in range(rng.randrange(181))] for _ in range(200))
    start = time.perf_counter()
    longest = 0.0
    for case in cases:
        before = time.perf_counter()
        result = solve(case)
        longest = max(longest, time.perf_counter() - before)
        assert sorted(i for b in result for i in b) == list(range(len(case)))
        assert all(b and sum(case[i] for i in b) <= 100 for b in result)
        assert result == solve(case)
    assert len(solve([60, 60, 40, 40])) == 2
    assert len(solve([51] * 90 + [49] * 90)) == 90
    print('PASS', len(cases), 'cases; deterministic; max_seconds', round(longest, 6),
          'total_seconds', round(time.perf_counter() - start, 3))

