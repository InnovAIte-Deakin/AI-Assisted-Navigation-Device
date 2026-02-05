import os, glob
from collections import Counter, defaultdict
from PIL import Image 

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 

TRAIN_LBL = os.path.join(BASE_DIR, "train_dataset/train/labels")
TRAIN_IMG = os.path.join(BASE_DIR, "train_dataset/train/images")
VAL_LBL   = os.path.join(BASE_DIR, "val_dataset/val/labels")
VAL_IMG   = os.path.join(BASE_DIR, "val_dataset/val/images")

CLASS_NAMES = ["book","books","monitor","office-chair","whiteboard","table","tv","couch"]

def scan_dataset(lbl_dir, img_dir):
    inst, imgs, unique = Counter(), defaultdict(set), set()
    resolutions = Counter()
    
    lbl_files = glob.glob(os.path.join(lbl_dir, "*.txt"))
    for p in lbl_files:
        fname = os.path.basename(p)
        unique.add(fname)
        with open(p, "r") as f:
            for ln in f:
                parts = ln.split()
                if not parts: continue
                try:
                    cid = int(float(parts[0]))
                    if 0 <= cid < len(CLASS_NAMES):
                        inst[cid] += 1
                        imgs[cid].add(fname)
                except: continue

    img_files = glob.glob(os.path.join(img_dir, "*.*"))
    img_basenames = {os.path.splitext(os.path.basename(i))[0] for i in img_files}
    lbl_basenames = {os.path.splitext(f)[0] for f in unique}
    
    orphans = (img_basenames - lbl_basenames) | (lbl_basenames - img_basenames)
    
    for i in img_files:
        try:
            with Image.open(i) as im:
                resolutions[im.size] += 1
        except: continue

    return inst, {k: len(v) for k, v in imgs.items()}, len(unique), len(orphans), resolutions

# Run Analysis
t_inst, t_imgs, t_uniq, t_orph, t_res = scan_dataset(TRAIN_LBL, TRAIN_IMG)
v_inst, v_imgs, v_uniq, v_orph, v_res = scan_dataset(VAL_LBL, VAL_IMG)

# --- Process Resolutions  ---
all_res = t_res + v_res
sorted_res = all_res.most_common(5) # Get top 5 most frequent resolutions

# Categorize sizes to see distribution
small = sum(count for res, count in all_res.items() if res[0] < 640 or res[1] < 640)
standard = all_res.get((640, 640), 0)
large = sum(count for res, count in all_res.items() if res[0] > 640 or res[1] > 640)

# --- Dashboard ---
print("\n" + "="*82)
print(f"  DATASET DIAGNOSTIC REPORT")
print("="*82)
header = f"  {'CLASS NAME':<15} | {'TRAIN':<7} | {'VAL':<5} | {'TOTAL':<7} | {'DENSITY':<8} | {'STATUS'}"
print(header)
print("-" * 82)

for i, name in enumerate(CLASS_NAMES):
    ti, vi = t_inst.get(i, 0), v_inst.get(i, 0)
    timg, tot = t_imgs.get(i, 0), ti + vi
    density = (ti / timg) if timg > 0 else 0
    
    if tot == 0:     status = "● EMPTY"
    elif tot < 50:   status = "! WEAK"
    elif vi == 0:    status = "! NO VAL"
    else:            status = "✓ HEALTHY"

    print(f"  {name:<15} | {ti:<7} | {vi:<5} | {tot:<7} | {density:>6.1f}x  | {status}")

print("-" * 82)
print(f"  UNIQUE LABELS   | Train: {t_uniq:<7} | Val: {v_uniq:<5} | Total: {t_uniq+v_uniq}")
print(f"  ORPHAN FILES    | Train: {t_orph:<7} | Val: {v_orph:<5} | <- Mismatched pairs")
print("-" * 82)

print("="*82)
# --- Resolutions ---
print(f"  RESOLUTION DISTRIBUTION:")
print("="*82)
print(f"  - Small (<640px)   : {small} images (May be blurry)")
print(f"  - Standard (640x)  : {standard} images")
print(f"  - Large (>640px)   : {large} images")
print(f"\n  TOP 5 MOST COMMON SIZES:")
for res, count in sorted_res:
    print(f"  {str(res):<18} : {count} images")
print("-"*82 + "\n")