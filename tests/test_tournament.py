"""Correctness checks independent of historical wall-clock measurements."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import judge
import verify


def load(name, initial=False):
    path = ROOT / ('round1' if initial else '') / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'{name}_{initial}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TournamentTests(unittest.TestCase):
    def test_saved_evidence(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            verify.main()
        report = json.loads(output.getvalue())
        self.assertTrue(report['passed'])
        self.assertEqual(report['saved_packings_checked'], 648)

    def test_validator_rejects_invalid_packings(self):
        for values, packing in [([50, 50], [[0, 0]]), ([60, 50], [[0, 1]]),
                                ([10], [[]]), ([10], [[True]]), ([10], [[1]])]:
            with self.subTest(values=values, packing=packing):
                self.assertIsNotNone(judge.validate(values, packing))
        self.assertIsNone(judge.validate([], []))
        self.assertIsNone(judge.validate([50, 50], [[0, 1]]))

    def test_all_versions_on_boundaries_and_small_exact_cases(self):
        rng = random.Random(730912)
        cases = [[], [100], [50, 50], [1]*180, [51]*180, [34]*180,
                 [66, 34]*90, [60, 60, 40, 40]]
        small = [[rng.randint(10, 90) for _ in range(rng.randint(6, 11))]
                 for _ in range(16)]
        for initial in [True, False]:
            for name in ['scarlet', 'cobalt', 'jade']:
                module = load(name, initial)
                for values in cases + small:
                    with self.subTest(agent=name, initial=initial, values=values):
                        supplied = values.copy()
                        packing = module.solve(supplied, 100)
                        self.assertEqual(supplied, values)
                        self.assertIsNone(judge.validate(values, packing))
                        self.assertEqual(packing, module.solve(values.copy(), 100))
                        if len(values) <= 11:
                            self.assertEqual(len(packing), judge.optimum_small(values))

    def test_peer_review_regressions(self):
        rng = random.Random(8873)
        values = []
        for _ in range(60):
            a = rng.randint(25, 49)
            b = rng.randint(25, 75-a)
            values.extend([a, b, 100-a-b])
        rng.shuffle(values)
        packing = load('cobalt').solve(values)
        self.assertIsNone(judge.validate(values, packing))
        self.assertEqual(len(packing), 60)
        frequency = [12, 15, 11, 12, 7, 10, 7, 13, 5, 10, 10, 8, 6,
                     2, 4, 7, 3, 2, 3, 3, 5, 4, 3, 1, 2]
        values = [w for w, count in zip(range(25, 50), frequency) for _ in range(count)]
        packing = load('jade').solve(values)
        self.assertIsNone(judge.validate(values, packing))
        self.assertEqual(len(packing), 55)
        for weight, expected in [(21, 45), (26, 60), (34, 90), (41, 90)]:
            values = [weight]*180
            packing = load('scarlet').solve(values)
            self.assertIsNone(judge.validate(values, packing))
            self.assertEqual(len(packing), expected)


if __name__ == '__main__':
    unittest.main()
