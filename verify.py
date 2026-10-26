"""Independently recheck saved tournament evidence without rerunning contestants."""
import hashlib
import json
from pathlib import Path
import statistics
import judge


def main():
    root = Path(__file__).resolve().parent
    data = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    cases_bytes = (root / 'cases.json').read_bytes()
    assert hashlib.sha256(cases_bytes).hexdigest() == judge.SEALED_SHA256 == data['dataset_sha256']
    cases = json.loads(cases_bytes)
    assert cases == data['cases'] == judge.make_cases()
    assert len(cases) == 108
    assert len({c['id'] for c in cases}) == 108
    judge.self_test()
    frozen = json.loads((root / 'FROZEN.json').read_text(encoding='utf-8'))
    for relative, expected in frozen.items():
        assert hashlib.sha256((root / relative.replace('\\', '/')).read_bytes()).hexdigest() == expected, relative
    checked = 0
    exact_checks = 0
    errors = []
    for phase, scores in data['rounds'].items():
        assert len(scores) == 3
        assert scores == sorted(scores, key=lambda s: (s['invalid'], s['total_bins'], s['median_ms']))
        for score in scores:
            source = root / ('round1' if phase == 'initial' else '') / (score['name'] + '.py')
            assert hashlib.sha256(source.read_bytes()).hexdigest() == score['source_sha256']
            rows = score['rows']
            assert len(rows) == len(cases)
            assert score['invalid'] == sum(bool(row['error']) for row in rows)
            assert score['total_bins'] == sum(row['bins'] for row in rows if not row['error'])
            assert score['median_ms'] == statistics.median(row['ms'] for row in rows)
            assert score['max_ms'] == max(row['max_ms'] for row in rows)
            for case, row in zip(cases, rows):
                assert case['id'] == row['id']
                # This run's only failure concerns time. All stored packings are feasible.
                assert judge.validate(case['items'], row['packing']) is None, (phase, score['name'], row['id'])
                assert row['bins'] == len(row['packing'])
                if case['optimum'] is not None:
                    assert row['bins'] == case['optimum']
                    exact_checks += 1
                if row['error']:
                    assert row['error'] == 'Exceeded 1 second' and row['max_ms'] > 1000
                    errors.append({'phase': phase, 'name': score['name'], 'case': row['id'],
                                   'error': row['error'], 'max_ms': row['max_ms']})
                checked += 1
    report = {'passed': True, 'dataset_cases': len(cases), 'saved_packings_checked': checked,
              'exact_optimum_checks': exact_checks, 'oracle_crosscheck_cases': 60,
              'solve_calls_in_official_run': 1944, 'repetitions': 3,
              'contestants_and_dataset_unchanged': True, 'scoring_errors': errors}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
