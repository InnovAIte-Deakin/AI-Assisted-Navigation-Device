# Interview evaluation validation record

Executed 15 October 2026, Australia/Sydney. Starting commit `fc55253`; local
branch `codex/a2i2-evaluation-evidence`. At the end of implementation validation,
no commit, remote push or merge had been performed. Publication is a follow-up.

## Results

| Check | Observed result | Scope |
| --- | --- | --- |
| Original inspector baseline | 36 passed, 2 skipped in 16.33 s | Before modifications; sandbox could not create two symlink fixtures |
| Expanded ML/deployment/registry/safety suite | **886 passed in 224.11 s** | Real fixture-based existing suites, including the initial new inspector/report/route tests; run outside restricted sandbox |
| Existing backend integration selection | **166 passed in 46.79 s** | Real FastAPI app wiring with mocked inference, runtime state/errors, adapters, depth/motion and guidance |
| Final focused changed-tool/route suite | **121 passed, 2 skipped in 5.85 s** | Final source, including an extra YAML fractional-ID regression test, evidence input/F1 hardening and actual guidance-processing threshold cases; two sandbox symlink fixtures skipped |
| Existing offline release-readiness CLI | **PASS** | Metadata consistency; registry production with recorded explicit human-team authorization; no live verification |
| New evidence CLI with local `best.pt` and chart | **MATCH**, 14 synthetic gate probes | Hash identity, saved metrics summarization and real pure-gate behavior; no inference |
| Chart inspection | Labels, scale, date, image count and historical qualifier verified | Plot comes from recorded per-class values; no synthetic metric values |
| `git diff --check` | Passed | Whitespace check; Git emitted ordinary CRLF conversion notices |
| Existing dirty files | **14/14 SHA-256 values unchanged** | Twelve pre-existing modified documents plus integrated-verification Markdown and the untracked package lock; other existing untracked directories were not edited |

The 886-test broad run preceded the final extra YAML-ID fixture, small
evidence summarizer hardening and two additional guidance-threshold fixtures.
The final focused suite validates those changes.
These counts overlap and must not be summed as a unique-test total. There are
34 added parametrized test cases across inspector, evidence and safety tests.
Hosted GitHub Actions was not run or claimed.

The backend environment uses Python 3.11.9, pytest 9.1.1, PyYAML 6.0.3,
Pillow 12.1.0, jsonschema 4.25.1 and matplotlib 3.10.8. Backend integration used
FastAPI 0.115.4 and httpx 0.27.0. Installed PyTorch 2.9.1+cu130 and Ultralytics
8.4.7 were not used for a new model inference/evaluation run.

## Exact commands

From the repository root, PowerShell:

```powershell
$wbPython = '.\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe'

# Final focused suite; the local run also passed with shell Python 3.11.9.
& $wbPython -m pytest -q -p no:cacheprovider ML_side/tests/test_inspect_candidate_dataset.py ML_side/tests/test_interview_evidence.py software_side/walkbuddy_reactNative/backend/tests/test_navigation_semantics.py

# Expanded suite. pythonpath makes the existing 'depth' package importable.
& $wbPython -m pytest -q -p no:cacheprovider -o pythonpath=ML_side ML_side/tests ML_side/deployment/tests ML_side/model_registry/tests software_side/walkbuddy_reactNative/backend/tests/test_navigation_semantics.py software_side/walkbuddy_reactNative/backend/tests/test_model_taxonomy_compatibility.py

# Existing backend integration selection; no model lifespan/startup executed.
& $wbPython -m pytest -q -p no:cacheprovider -o pythonpath=software_side/walkbuddy_reactNative/backend software_side/walkbuddy_reactNative/backend/tests/test_ml_inference_integration.py software_side/walkbuddy_reactNative/backend/tests/test_ai_service_helpers.py software_side/walkbuddy_reactNative/backend/tests/test_ml_runtime.py software_side/walkbuddy_reactNative/backend/tests/test_vision_adapter.py software_side/walkbuddy_reactNative/backend/tests/test_message_reasoning.py software_side/walkbuddy_reactNative/backend/tests/test_vision_depth_integration.py software_side/walkbuddy_reactNative/backend/tests/test_depth_adapter.py software_side/walkbuddy_reactNative/backend/tests/test_motion_awareness.py

& $wbPython -m ML_side.tools.build_interview_evidence --model ML_side/models/best.pt --chart
& $wbPython -m ML_side.tools.release_readiness --candidate WB-OD-NAV-001 --out-dir docs/interview/evidence/release-readiness
git diff --check
```

The broad command will collect three additional cases on the final source compared
with the recorded broad run. Ordinary runs outside Codex's sandbox are expected
to use normal temporary-directory and loopback permissions. `-p no:cacheprovider`
avoids writing pytest caches into the shared checkout.

## Environmental problems encountered and resolved

- Shell Python lacks FastAPI, PyTorch, Ultralytics, matplotlib and jsonschema.
  Attempting the existing release-readiness CLI with it failed during import
  (`ModuleNotFoundError: jsonschema`). The existing backend virtual environment
  supplied the needed dependencies; no package installation was performed.
- A broad run without an explicit ML-side Python path stopped at collection
  (`ModuleNotFoundError: depth`). The reproduction command includes
  `-o pythonpath=ML_side`; no production import code was changed.
- Restricted Windows sandbox temporary paths exceeded the platform's path limit
  in some existing release-builder fixtures (`WinError 206`). Its loopback
  restrictions also stalled `asyncio.run` while creating the Windows event loop's
  socket pair. These unsuccessful/interrupted runs are not reported as passes.
  The broad and HTTP integration checks passed outside that restricted sandbox
  using the authorized test runner.
- The two early-return chat tests now advance the coroutine directly and assert
  that it finishes before asynchronous work. This tests route branching and
  preserves the no-LLM assertion without requiring a local socket. Separate
  existing FastAPI integration tests cover transport/wiring.

## Files changed by this task

| File or group | Purpose |
| --- | --- |
| `ML_side/tools/inspect_candidate_dataset.py` | Split distributions, coverage/imbalance, CSV and audit failure handling; version 1.1.0 |
| `ML_side/tests/test_inspect_candidate_dataset.py` | Ten new collected fixture cases including fractional YAML class IDs |
| `ML_side/tools/build_interview_evidence.py` | Offline recorded-evidence/provenance reporter and optional scientific chart |
| `ML_side/tests/test_interview_evidence.py` | Fourteen collected cases for provenance mismatches, invalid metrics, missing weights, deterministic output and explicit unavailable evidence |
| `software_side/walkbuddy_reactNative/backend/tests/test_navigation_semantics.py` | Ten collected characterization cases and socket-free synchronous-branch helper |
| `ML_side/datasets/README.md` | Inspector 1.1 fields, interpretation and failure behavior |
| `.github/workflows/ml-safety.yml` | Select inspector and evidence-report tests in existing model-free gate |
| `ML_side/requirements-ci.txt` | Pin the already-verified Pillow version so CI can verify corrupt-image fixtures |
| `docs/interview/A2I2_EVALUATION_BRIEF.md` | Requested nine-part handoff, interview explanation and hypothetical manufacturing analogy |
| `docs/interview/REPOSITORY_EVALUATION_AUDIT.md`, `VALIDATION.md` | Method, source inventory, expected/observed failures, execution record and limits |
| `docs/interview/evidence/interview_evidence.json` | Reproducible source digests, historical metrics, local identity and synthetic gate results |
| `docs/interview/evidence/recorded_per_class_metrics.csv`, `.png` | Recorded metrics with explicitly derived per-class F1 and labelled chart |
| `docs/interview/evidence/release-readiness/` | JSON/Markdown output of existing offline readiness tool |

## Unavailable or intentionally unexecuted validation

No real dataset integrity/leakage audit, retraining, fresh labelled scoring,
production-weight modification, live endpoint check, mobile acceptance, OCR
accuracy evaluation, predictive-path evaluation, LLM response benchmark or
manufacturing/Overseer test was performed. Synthetic fixtures and pre-existing
historical observations are labelled separately throughout the brief.

## Publication preflight follow-up

The publication review isolated 16 upgrade files and excluded pre-existing team
edits, presentation builds, integrated-device evidence and the unrelated package
lock. Source fingerprints initially differed from staged Git blobs because of
Windows CRLF checkout conversion. The reporter now declares and applies CRLF-to-LF
normalization for source text only. Exact model checksums and historical metric
values remain unchanged. An additional regression case verifies both conventions.
The original 34-case addition count above describes the implementation handoff;
the publication change adds one further collected case.

After this correction, the focused command above passed **122 tests**, with two
sandbox symlink fixtures skipped, in 14.58 s. The offline release-readiness
preflight passed again. Comparison against the previously staged report confirmed
that recorded metrics, historical CSV rows, local artifact identity and all 14
synthetic gate results were unchanged.
