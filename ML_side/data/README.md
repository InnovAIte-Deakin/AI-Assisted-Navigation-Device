# Dataset — Current State 
This README describes the **current on-repo dataset state** as it exists today.  
The dataset is intentionally stored inside the repo for now to:
- reduce onboarding friction
- allow direct local + notebook-based experimentation
- keep experiments inspectable without external dependencies

## Format
- Annotation format: **YOLO (bounding boxes)**
- Splits: **train / val**
- Labels: one `.txt` per image
- No orphaned image–label pairs

## Classes Present
From `dataset_analyze.py` output:
| Class | Train | Val | Total |
|------|------:|----:|------:|
| book | 5 | 0 | 5 |
| books | 1553 | 125 | 1678 |
| monitor | 460 | 50 | 510 |
| office-chair | 181 | 36 | 217 |
| whiteboard | 582 | 31 | 613 |
| table | 553 | 31 | 584 |
| tv | 531 | 26 | 557 |
| couch | 1053 | 50 | 1103 |
- **Total:** 3487  
- **Train:** 3285 (Images + Labels)  
- **Val:** 202 (Images + Labels) 
All classes except `book` are currently well-represented.

## Resolution Distribution
- Small (<640px): 1024 images  
- Standard (640×640): 643 images  
- Large (>640px): 2030 images  
Most common image sizes:
- 640×640 (643)
- 1024×768 (210)
- 1024×683 (119)
- 1000×1000 (73)
- 3024×4032 (69)
Images are resized at training time.

## Tooling
- `dataset_analyze.py`  
  Used to inspect:
  - class counts
  - train/val balance
  - orphan files
  - image resolutions

The README reflects the output of this script.

## Notes
- Dataset is stored **directly in the repo**.
- Intended for local training, experimentation, and reproducibility.
- Dataset contents may change; this README should be updated alongside changes.

