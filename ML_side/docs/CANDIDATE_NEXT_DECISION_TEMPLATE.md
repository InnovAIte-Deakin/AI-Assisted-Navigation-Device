# Candidate Next-Decision Template

Use this template before proposing a controlled dataset revision or training a
new candidate. Complete it from evidence; do not tune on the held-out split.

## Decision scope

- Candidate under review:
- Exact artifact SHA-256:
- Controlled dataset release:
- Decision owner and date:
- Proposed decision: retain / investigate / controlled dataset revision / do not train:

## Required evidence

| Evidence area | Repository or controlled evidence reference | Finding | Decision impact |
| --- | --- | --- |
| Pole geometry analysis |  |  |  |
| Train/validation data-quality analysis |  |  |  |
| Class support and distribution |  |  |  |
| Labelling-quality review |  |  |  |
| Failure-mode analysis |  |  |  |
| Expected benefit of a dataset revision |  |  |  |

## Guardrails

- Held-out test data is evaluation-only. It must not be used to select
  augmentations, thresholds, training duration, model architecture, or a new
  candidate.
- Train a new candidate only when the evidence justifies a controlled dataset
  revision with documented lineage, quality checks, and split isolation.
- State the expected benefit and the measurable acceptance criterion before
  training. A low metric alone is not a sufficient causal explanation.
- If geometry evidence is pending or an implementation is unmerged, record it
  as pending. Do not copy it, infer its result, or treat it as merged evidence.
- This template does not require Candidate 2. It supports a decision only when
  evidence makes a controlled revision justified.
