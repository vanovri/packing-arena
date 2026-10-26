# Packing Arena

A reproducible AI-assisted algorithm tournament for one-dimensional bin packing. Three independent Codex agents build solutions, review one peer, revise once, and compete on the same sealed synthetic dataset. An offline dashboard lets you inspect the scores and every packing.

[Live demo](https://vanovri.github.io/packing-arena/) · [Recorded results](results.json) · [Tournament rules](RULES.txt)

## What this project demonstrates

- A deterministic Python judge with capacity, index, input-mutation, and repeatability checks.
- An independent exact oracle for small cases, cross-checked against exhaustive search.
- A before-and-after comparison with original source snapshots and written peer reviews.
- A responsive, dependency-free results explorer and a verified GitHub Pages deployment.

This project was built with AI assistance. Codex agents generated the algorithms, reviews, judge, and interface under a human brief and publication approval. Scarlet, Cobalt, and Jade are three agents inheriting the same parent model. They are not three different model families.

## Recorded experiment

The input contains 0–180 integer weights from 1 to 100. Each bin holds at most 100. A solution returns original item indices, each exactly once. Ranking compares failed cases first, then total bins on passing cases, then median runtime. A call exceeding one second fails that case.

The dataset has 108 synthetic cases in eight groups. Each of six source versions ran three times, for 1,944 calls. Contestant order rotated across repetitions. Timing excludes imports, validation, and process startup.

| Final rank | Agent | Output bins across all cases | Failed cases | Median call time |
| --- | --- | ---: | ---: | ---: |
| 1 | Jade | 3,321 | 0 | 0.1346 ms |
| 2 | Scarlet | 3,321 | 0 | 0.2508 ms |
| 3 | Cobalt | 3,321 | 1 | 0.4188 ms |

Best-fit decreasing used 3,333 bins. All stored packings satisfy capacity and index requirements. Cobalt's final version exceeded the one-second deadline on C017, with a maximum observed time of 1,632.2889 ms. Its official partial bin score is 3,234 across the 107 passing cases. That partial score is not a quality advantage.

All three agents matched the exact optimum on the 29 cases for which an exact optimum was computed. Peer feedback improved known review examples, but did not reduce the total bin count on the hidden dataset. Jade wins this recorded run through the timing tie-breaker.

## Run locally

Python 3.10 or newer is sufficient. No third-party Python packages are required.

```sh
git clone https://github.com/vanovri/packing-arena.git
cd packing-arena
python verify.py
python -m unittest discover -s tests -v
python render.py
python -m http.server 8000 --bind 127.0.0.1
```

Open `http://127.0.0.1:8000/`. You can also open `index.html` directly without a server.

`verify.py` rechecks all 648 saved packings, 174 exact-optimum comparisons, source hashes, rankings, and the sealed dataset. It also cross-checks the oracle on 60 independently enumerated cases. It verifies the recorded evidence without rerunning the entire tournament.

To rerun the full tournament, use a separate copy of the checkout, then run:

```sh
python judge.py --root . --cases cases.json
python render.py
```

The full run replaces `results.json`. Runtime and the resulting timing ranking can change across machines and system load. The published timing measurements came from a Windows host using Python 3.14. CI validates correctness and stored evidence; CI does not reproduce the original timing measurements.

## Evidence and layout

| File | Purpose |
| --- | --- |
| `scarlet.py`, `cobalt.py`, `jade.py` | Revised contestant implementations |
| `round1/` | Original implementations before peer review |
| `judge.py` | Dataset generator, baseline, exact oracle, runner, and validator |
| `cases.json`, `results.json` | Sealed inputs and recorded per-case outputs |
| `FROZEN.json` | Pre-run hashes of contestants, judge, and input bytes |
| `review-*.txt` | Circular peer reviews in Indonesian |
| `REVISION-NOTES.txt`, `judge-run.log` | Revision summary and execution record |
| `verify.py`, `tests/` | Evidence verification and runnable correctness tests |
| `render.py`, `build_site.py` | Offline dashboard and allowlisted static-site build |

The original dataset hash is `ffa9821b3962c960c2d41642a1bac054f862fca7f0fb66a15fbe925aabbbbdf1`. Git preserves original file bytes so Windows line endings do not invalidate the frozen evidence. The verifier normalizes manifest path separators for cross-platform checks.

## Limits

All inputs are synthetic. This is a small experimental benchmark, not a production logistics optimizer or a comparison of model families. Large cases have lower bounds rather than proven optima. Fixed operation budgets can miss better packings. The recorded three repetitions are not enough to establish statistically significant speed differences or universal runtime guarantees.

The original hidden dataset is now public for reproducibility. It should not serve as an unseen test set for future algorithm tuning. Use a new precommitted dataset for a new tournament.

## License

[MIT](LICENSE).
