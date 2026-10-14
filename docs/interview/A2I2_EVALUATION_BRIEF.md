# A2I2 interview evidence brief

Prepared 15 October 2026 for the 20-minute interview on Friday, 16 October 2026.
Role title supplied by the applicant: “Curating Real-World Manufacturing
Evaluation Datasets to Assess the AI Models and Agentic Harnesses behind Overseer.”

## 1. What WalkBuddy does

WalkBuddy is a team-built AI-assisted navigation project for visually impaired
users. A mobile camera sends images to a Python/FastAPI backend; object detection,
OCR and direction/motion processing feed guidance. A deterministic hazard gate
can override the LLM response path. The phone speaks the returned text.

The production registry names `WB-OD-NAV-001` v0.1.0 with eight classes:
person, stairs, door, chair, table, pole, bicycle and vehicle. Its committed
training configuration references YOLO26n initial weights; YOLOv8n was the
historical cohort-1 selection. Avoid describing current weights as verified
YOLOv8n. This project is not a validated substitute for a mobility aid.

## 2. My role and the team's contributions

“I led the ML and deployment stream” is the applicant's supplied role description.
Repository history corroborates substantial work under the Lorenzo account:

| Contribution evidence | Commit examples |
| --- | --- |
| Controlled dataset release and immutable training workspace checks | `2a35bf3`, `0a33d97`, `68955b4` |
| Held-out split selection and corrected image-count reporting | `e337da1`, `38980c0` |
| Model registry, evaluation linkage and runtime acceptance evidence | `5a5eced`, `e467631`, `d870b2c` |
| Runtime soak, release-readiness and CI deployment checks | `7d71485`, `c4a68fc`, `1a78b64` |

Commit authorship records contributions, not sole authorship or proof of who
executed every experiment. The historical ML reports credit Bravine Cheruiyot;
GuvencEdu's commits `2f7c0ea` and `0ae2b5c` implement/integrate `/ml/navigate`;
Rishikaandh's `b3aea90` integrates relative depth; recent mobile voice work is
credited to praseth. The application, source datasets, historical training and
mobile integration are shared team work. These interview enhancements were
prepared with AI assistance and validated with reproducible checks.

## 3. Improvements completed for this interview

- Extended the existing dataset inspector with per-split class/image counts,
  annotation shares, absent-class coverage, imbalance ratios and CSV output.
  Added failures for empty declared splits, malformed taxonomy/`nc`, ambiguous
  image-label stems and invalid orphan labels. Preserved the legacy analyzer.
- Added an offline evidence summarizer that checks evaluation/registry identity,
  fingerprints sources, optionally hashes local weights and derives explicitly
  labelled per-class F1. It emits JSON, CSV and a chart from saved measurements.
- Added deterministic tests for audit failures and warning boundaries, motion
  loss, empty-output wording and scene-query routing. Added the new ML tooling
  tests to the existing safety CI workflow.
- Created an [engineering audit](REPOSITORY_EVALUATION_AUDIT.md) and
  [validation record](VALIDATION.md). Product policy and model artifacts remain
  team-owned; the discovered route issues are documented for review.

## 4. What the evidence proves

The local `best.pt` bytes match the production registry and the saved evaluator's
model SHA-256. The existing offline release-readiness gate passes. This proves
identity and consistency of the available artifacts, not a fresh accuracy result
or the identity of a currently running backend.

The **recorded 2 September 2026 held-out test evaluation**, on **3,497 images**,
reports precision **0.6960**, recall **0.6122**, mAP@50 **0.6685**, and
mAP@50:95 **0.4357**. These were not remeasured for this interview. The new chart
and [metrics CSV](evidence/recorded_per_class_metrics.csv) reproduce that summary.
Per-class F1 and its unweighted class mean are explicitly labelled algebraic
derivations from recorded P/R. Recorded aggregate F1 and micro/support-weighted
F1 remain unavailable; the required recorded value or counts/support are missing.

Fixture tests prove tooling and deterministic boundary behavior. Fourteen
synthetic gate probes cover the eight classes, alias, confidence boundary,
direction, unsupported stationary label and approaching unknown object. They
are not fourteen measured real-world hazard scenarios.

## 5. Most meaningful failures

The strongest recorded model finding is **pole precision 5.48%**, recall 51.84%,
AP@50 17.55% and AP@50:95 14.76%. That suggests serious false-alarm limitations
under the recorded evaluator settings. It does not establish the cause, or the
false-alarm rate of the deployed warning threshold. Person recall is also low
at 37.73%, despite precision of 89.14%.

The system tests expose separate problems: empty detections, or stairs detections
below the guidance filter of 0.3, can produce “Path clear”; `/chat` normalization
drops motion fields used by the hazard gate;
“Is it safe to move ahead?” takes the scene-description branch before the stop
override; detections between confidence 0.25 and 0.5 receive no stop override
from that gate. Stationary potholes are outside the model/policy coverage.
See the audit's expected-versus-observed table for exact scope and recommendations.

## 6. Limitations and unresolved work

No controlled dataset was present in this checkout. Therefore real split counts,
imbalance, invalid labels, duplicate images and group leakage were not measured.
The evaluator summary lacks a dataset content digest, release ID, class instance
support, raw TP/FP/FN and evaluator environment/seed. The registry's release
claim and configuration seed 42 are recorded separately, not inferred into it.

There was no retraining, fresh model scoring, download, live backend launch,
phone test, OCR accuracy study, user study or LLM/agent benchmark. Existing
runtime-soak and benchmark evidence is historical. The historical seven-class
baseline and cohort-1 CSVs cannot be compared directly with this eight-class
model. The old HTTP test harness still targets a retired contract. Product
warning-policy fixes need coordinated backend/accessibility review.

## 7. Reproduce and demonstrate

Run from the repository root in PowerShell. Use the existing backend environment:

```powershell
$wbPython = '.\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe'
& $wbPython -m pytest -q -p no:cacheprovider ML_side/tests/test_inspect_candidate_dataset.py ML_side/tests/test_interview_evidence.py software_side/walkbuddy_reactNative/backend/tests/test_navigation_semantics.py
& $wbPython -m ML_side.tools.build_interview_evidence --model ML_side/models/best.pt --chart
& $wbPython -m ML_side.tools.release_readiness --candidate WB-OD-NAV-001 --out-dir docs/interview/evidence/release-readiness
```

On a machine without weights or plotting dependencies, omit `--model` and
`--chart`; JSON/CSV and synthetic gate probes still work. A requested missing
model is `NOT_CHECKED`; a different checksum is `MISMATCH` and exits nonzero.
Python 3.11 plus the repository's lightweight CI requirements supports focused
model-free tests. Pillow checks skip explicitly if unavailable. Do not silently
substitute shell Python for the configured backend interpreter.

For a five-minute demonstration, run the focused tests, show the JSON evidence
kinds/local checksum result, then open the chart and explain pole precision.
Show the route characterization tests and explain why passing tests can
confirm undesirable behavior. Finish with the unmeasured data-quality boundary.

The expanded fixture-based suite is:

```powershell
& $wbPython -m pytest -q -p no:cacheprovider -o pythonpath=ML_side ML_side/tests ML_side/deployment/tests ML_side/model_registry/tests software_side/walkbuddy_reactNative/backend/tests/test_navigation_semantics.py software_side/walkbuddy_reactNative/backend/tests/test_model_taxonomy_compatibility.py
```

For an actual dataset audit **only after obtaining approved controlled data**:

```powershell
# Replace these variables with real supplied paths; examples are not a dataset.
$wbDataset = 'D:\controlled-datasets\approved-release'
$wbReports = 'D:\controlled-reports\interview-audit'
& $wbPython ML_side/tools/inspect_candidate_dataset.py --dataset-root $wbDataset --dataset-yaml "$wbDataset\dataset.yaml" --group-map "$wbDataset\groups.json" --output-dir $wbReports
```

The YAML must use relative split paths beneath that root; reports must be
outside it. The group map links relative image paths to real session/sequence
IDs. No target-class mapping is inferred: supply reviewed `--metadata` when
target mapping is needed. The command writes JSON, Markdown and class CSV; it
does not change labels or weights. Fixtures below the new tests reproduce each
new audit failure; they do not establish failures in the external release.

To verify contribution and historical metric claims:

```powershell
git show --stat 2a35bf3
git show --stat c4a68fc
Get-FileHash ML_side/models/best.pt -Algorithm SHA256
Get-Content ML_side/experiments/cohort-1/yolo_v8n/results.csv | Select-Object -Last 1
```

## 8. A natural 90-second explanation

“WalkBuddy is a team project that uses computer vision, OCR and a FastAPI backend
to provide navigation guidance for visually impaired users. I led the ML and
deployment stream, with contributions around dataset releases, model evaluation
and deployment verification.

For this interview, I used AI assistance to strengthen the evaluation evidence.
I started with what the repository could actually prove. I checked that the local
weights match the registry and the saved held-out evaluation. Those are historical
results, not a fresh accuracy claim.

I extended our existing dataset inspector to expose split coverage and class
imbalance, export CSV, and reject silent failures such as empty splits and
malformed orphan labels. I tested those changes with synthetic fixtures because
the controlled dataset wasn't available here.

The saved metrics highlight weak pole precision. Separately, integration tests
show that empty detections can become ‘Path clear’ and that a chat boundary drops
motion context. That demonstrates why model metrics don't establish system safety.

The connection to this internship is the method: preserve provenance, define
evaluation criteria, separate data and model failures from harness failures, and
make every claim reproducible while being explicit about what remains unknown.”

## 9. Five realistic technical questions

| Question | Concise answer |
| --- | --- |
| How would you prevent evaluation leakage? | Group by original session/video/source sequence before splitting; hash exact content; inspect near duplicates and source overlap; keep test data out of tuning. A SHA check alone misses re-encoded or adjacent frames. |
| Why report precision, recall, AP and F1 separately? | They expose different tradeoffs. AP spans confidence thresholds; runtime warnings use an operating point. I can derive per-class F1 from saved P/R, but cannot recover micro F1 or uncertainty without counts/support. |
| How do you know these results belong to this model? | Registry, saved evaluator and local weights have the same SHA-256 and ordered taxonomy. That binds identity. The missing dataset digest means I cannot independently establish the original evaluation input bytes. |
| What did passing integration tests tell you? | They reproduce specific route and gate behavior, including undesirable outcomes. Model accuracy, warning accuracy, transport reliability and user outcomes need different tests. Stubs do not prove live phone reliability. |
| How would this transfer to manufacturing/agent evaluation? | Define reviewed representative scenarios and expected decisions, preserve data/model/harness versions, hold out source groups, capture tool traces and outcomes, and classify failures. I would validate model predictions and final actions separately. I have not benchmarked Overseer. |

## Manufacturing analogy — hypothetical, not an Overseer implementation claim

Imagine evaluating surface-defect inspection plus an agent that selects an
inspection tool and prepares a disposition recommendation. Curate scenarios by
machine, batch, material, lighting and defect severity; adjudicate ambiguous
labels; split related batches/sequences together. Record dataset identity,
model/harness/prompt/tool versions and repeat settings. Score defect predictions
separately from tool selection, evidence use, final action, abstention, latency
and recovery. An accurate classifier can still be wrapped by a harness that
drops context or issues an unsafe conclusion. This is a proposed evaluation
methodology, not knowledge of Overseer's architecture or measured performance.
