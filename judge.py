"""Reproducible, held-out 1D bin-packing tournament. Python standard library only."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from collections import Counter
from functools import lru_cache

SEED = 6101242026
SEALED_SHA256 = 'ffa9821b3962c960c2d41642a1bac054f862fca7f0fb66a15fbe925aabbbbdf1'
NAMES = ['scarlet', 'cobalt', 'jade']


def bfd(items, capacity=100):
    bins, loads = [], []
    for i in sorted(range(len(items)), key=lambda i: (-items[i], i)):
        fits = [j for j, load in enumerate(loads) if load + items[i] <= capacity]
        if fits:
            j = max(fits, key=lambda j: loads[j])
            bins[j].append(i)
            loads[j] += items[i]
        else:
            bins.append([i])
            loads.append(items[i])
    return bins


def optimum_small(items):
    weights = sorted(items, reverse=True)
    best = len(bfd(items))
    lower = max(math.ceil(sum(items) / 100), sum(x > 50 for x in items))
    if best == lower:
        return best
    loads = []

    def visit(i):
        nonlocal best
        if best == lower:
            return
        if i == len(weights):
            best = min(best, len(loads))
            return
        w = weights[i]
        seen = set()
        for j, load in enumerate(loads):
            if load in seen or load + w > 100:
                continue
            seen.add(load)
            loads[j] += w
            visit(i + 1)
            loads[j] -= w
        if len(loads) + 1 < best:
            loads.append(w)
            visit(i + 1)
            loads.pop()

    visit(0)
    return best


def make_cases():
    rng = random.Random(SEED)
    cases = []

    def add(family, items, exact=False):
        cases.append({'id': f'C{len(cases) + 1:03}', 'family': family,
                      'items': items, 'lower_bound': max(math.ceil(sum(items)/100),
                      sum(x > 50 for x in items)),
                      'optimum': optimum_small(items) if exact else None})

    edges = [[], [100], [1], [50, 50], [100]*180, [1]*180,
             [51]*180, [33]*180, [50]*180, [66, 34]*90,
             [60, 60, 40, 40, 40, 20, 20, 20], [99, 1]*90]
    for items in edges:
        add('edge', items, len(items) <= 14)
    for family in ['uniform', 'small', 'large', 'near_third', 'complements', 'mixed']:
        for trial in range(12):
            n = [20, 40, 80, 120, 180][trial % 5]
            if family == 'uniform':
                items = [rng.randint(1, 100) for _ in range(n)]
            elif family == 'small':
                items = [rng.randint(1, 25) for _ in range(n)]
            elif family == 'large':
                items = [rng.randint(40, 80) for _ in range(n)]
            elif family == 'near_third':
                items = [rng.choice([24, 25, 26, 32, 33, 34, 49, 50, 51]) for _ in range(n)]
            elif family == 'complements':
                items = []
                for _ in range(n // 2):
                    a = rng.randint(1, 99)
                    items.extend([a, 100-a])
            else:
                items = [rng.choice([rng.randint(1, 10), rng.randint(25, 40),
                                     rng.randint(55, 75)]) for _ in range(n)]
            rng.shuffle(items)
            add(family, items)
    for _ in range(24):
        add('exact_small', [rng.randint(10, 80) for _ in range(rng.randint(8, 14))], True)
    return cases


def validate(items, packing):
    if not isinstance(packing, list):
        return 'Output must be a list'
    flat = []
    for box in packing:
        if not isinstance(box, list) or not box:
            return 'Each bin must be a nonempty list'
        if any(type(i) is not int or i < 0 or i >= len(items) for i in box):
            return 'Invalid item index'
        if sum(items[i] for i in box) > 100:
            return 'Capacity exceeded'
        flat.extend(box)
    if Counter(flat) != Counter(range(len(items))):
        return 'Missing or duplicated item'
    return None


def worker(module_path, cases_path, trial):
    spec = importlib.util.spec_from_file_location('contestant', module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cases = json.loads(Path(cases_path).read_text(encoding='utf-8'))
    order = list(range(len(cases)))
    random.Random(SEED + trial).shuffle(order)
    records = []
    for idx in order:
        case = cases[idx]
        supplied = case['items'].copy()
        start = time.perf_counter_ns()
        try:
            packing = mod.solve(supplied, 100)
            elapsed = (time.perf_counter_ns() - start) / 1e6
            error = validate(case['items'], packing)
            if supplied != case['items']:
                error = 'Input mutated'
            if elapsed > 1000:
                error = 'Exceeded 1 second'
        except Exception as exc:
            elapsed = (time.perf_counter_ns() - start) / 1e6
            packing, error = [], f'{type(exc).__name__}: {exc}'
        records.append({'id': case['id'], 'bins': len(packing) if isinstance(packing, list) else None,
                        'ms': elapsed, 'error': error, 'packing': packing})
    print(json.dumps(records))


def run(root, cases_path):
    cases_bytes = cases_path.read_bytes()
    if hashlib.sha256(cases_bytes).hexdigest() != SEALED_SHA256:
        raise ValueError('Dataset differs from the pre-review commitment')
    cases = json.loads(cases_bytes)
    results = {'seed': SEED, 'dataset_sha256': hashlib.sha256(cases_bytes).hexdigest(),
               'rules': 'Rank: invalid cases, total bins, median runtime. 1 second per case.',
               'cases': cases, 'rounds': {}, 'baseline': [len(bfd(c['items'])) for c in cases]}
    for phase, folder in [('initial', root / 'round1'), ('final', root)]:
        phase_results = {name: [] for name in NAMES}
        for trial in range(3):
            order = NAMES[trial:] + NAMES[:trial]
            for name in order:
                proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                                       str(folder / f'{name}.py'), '--cases', str(cases_path),
                                       '--trial', str(trial)], capture_output=True, text=True, timeout=180)
                if proc.returncode:
                    raise RuntimeError(f'{phase}/{name}: {proc.stderr}')
                phase_results[name].append(json.loads(proc.stdout))
                print(f'{phase} trial {trial + 1} {name}: done', flush=True)
        summaries = []
        for name in NAMES:
            trials = [{r['id']: r for r in rows} for rows in phase_results[name]]
            rows = []
            for case in cases:
                entries = [trial[case['id']] for trial in trials]
                row = entries[0].copy()
                row['ms'] = statistics.median(e['ms'] for e in entries)
                row['max_ms'] = max(e['ms'] for e in entries)
                errors = [e['error'] for e in entries if e['error']]
                if any(e['packing'] != row['packing'] for e in entries):
                    errors.append('Nondeterministic output')
                row['error'] = '; '.join(sorted(set(errors))) or None
                if not row['error'] and case['optimum'] is not None:
                    assert row['bins'] >= case['optimum'], 'Oracle disagreement requires investigation'
                rows.append(row)
            valid = [r for r in rows if not r['error']]
            summaries.append({'name': name, 'invalid': len(rows)-len(valid),
                              'total_bins': sum(r['bins'] for r in valid),
                              'median_ms': statistics.median(r['ms'] for r in rows),
                              'max_ms': max(r['max_ms'] for r in rows),
                              'source_sha256': hashlib.sha256((folder / f'{name}.py').read_bytes()).hexdigest(),
                              'rows': rows})
        summaries.sort(key=lambda s: (s['invalid'], s['total_bins'], s['median_ms']))
        results['rounds'][phase] = summaries
    (root / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({phase: [{k:v for k,v in s.items() if k != 'rows'} for s in scores]
                      for phase, scores in results['rounds'].items()}, indent=2))


def self_test():
    assert optimum_small([]) == 0
    assert optimum_small([60, 60, 40, 40]) == 2
    assert optimum_small([40, 40, 40, 30, 30, 20]) == 2
    assert validate([50, 50], [[0, 1]]) is None
    assert validate([50, 50], [[0, 0]])
    assert validate([60, 50], [[0, 1]])
    assert validate([100], [[True]])
    assert validate([], []) is None

    @lru_cache(None)
    def exhaustive(weights, loads=()):
        if not weights:
            return len(loads)
        w, *rest = weights
        answers = [exhaustive(tuple(rest), tuple(sorted(loads + (w,))))]
        for j, load in enumerate(loads):
            if load + w <= 100:
                changed = list(loads)
                changed[j] += w
                answers.append(exhaustive(tuple(rest), tuple(sorted(changed))))
        return min(answers)

    rng = random.Random(82367)
    for _ in range(60):
        weights = [rng.choice([20, 30, 40, 50, 60, 70, 80]) for _ in range(rng.randrange(9))]
        assert optimum_small(weights) == exhaustive(tuple(sorted(weights, reverse=True)))
        assert validate(weights, bfd(weights)) is None


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--worker')
    p.add_argument('--cases', type=Path, default=Path(__file__).with_name('cases.json'))
    p.add_argument('--trial', type=int, default=0)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = p.parse_args()
    if args.worker:
        worker(args.worker, args.cases, args.trial)
    else:
        self_test()
        if args.prepare:
            args.cases.write_text(json.dumps(make_cases(), indent=2), encoding='utf-8')
            print('Dataset sealed:', hashlib.sha256(args.cases.read_bytes()).hexdigest())
        else:
            run(args.root, args.cases)
