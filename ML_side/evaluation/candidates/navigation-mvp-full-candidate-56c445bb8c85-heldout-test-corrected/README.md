# Corrected held-out evaluation evidence

## Status

This package preserves existing corrected evaluation evidence; it was not produced by a rerun. It does not approve the candidate for production.

## Authoritative artifact

`summary.json` is the evaluator's versioned machine-readable summary. It was copied byte-for-byte from the corrected evaluator output for run `navigation-mvp-full-candidate-56c445bb8c85`.

Source and durable-copy SHA-256: `16b05cbdf0ca11116f27ce196c13697ec13018004a4cfd69a6a773212b42b8da`.

The summary records `best.pt` with SHA-256 `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`, the approved ordered eight-class taxonomy, labelled validation on the `test` split, and a validation image count of 3497. It does not contain the obsolete validation-image-count value of 8.

## Recorded provenance limits

The original evaluator summary does not record a dataset-release identifier, held-out instance count, or candidate-validation report linkage. Those values are intentionally not added or inferred here. The source directory name identifies the associated run as `navigation-mvp-full-candidate-56c445bb8c85`.

## Intended use

`summary.json` is loadable by `ML_side/tools/compare_model_evaluations.py` and is the future registry evaluation-evidence reference. A compatible canonical eight-class baseline, approved promotion policy, matching candidate-validation evidence, and a PASS comparison remain required before any production transition.
