from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .database import PipelineDatabase
from .models import StageResult, StageStatus
from .quarantine import quarantine_asset
from .utils import copy_or_link


def exact_duplicates(
    db: PipelineDatabase, run_id: str, invalid_root: Path
) -> StageResult:
    rows = db.rows(
        """SELECT asset_id, source_id, original_relative_path, original_sha256, raw_label_path
           FROM assets WHERE run_id=? AND status='registered'
           ORDER BY source_id, original_relative_path""",
        (run_id,),
    )
    groups: dict[str, list[object]] = defaultdict(list)
    for row in rows:
        groups[str(row["original_sha256"])].append(row)
    duplicate_count = 0
    same_folder_count = 0
    for digest, members in groups.items():
        if len(members) < 2:
            continue
        representative = min(
            members,
            key=lambda row: (
                row["raw_label_path"] is None,
                str(row["source_id"]),
                str(row["original_relative_path"]).lower(),
            ),
        )
        cluster_id = "exact-" + digest[:16]
        representative_parent = Path(str(representative["original_relative_path"])).parent.as_posix().lower()
        for row in members:
            asset_id = str(row["asset_id"])
            decision = "keep" if asset_id == representative["asset_id"] else "quarantine"
            db.connection.execute(
                """INSERT OR REPLACE INTO duplicate_candidates
                   (run_id, cluster_id, asset_id, representative_asset_id, kind, distance, decision)
                   VALUES (?, ?, ?, ?, 'exact', 0, ?)""",
                (run_id, cluster_id, asset_id, representative["asset_id"], decision),
            )
            if decision == "quarantine":
                duplicate_count += 1
                parent = Path(str(row["original_relative_path"])).parent.as_posix().lower()
                if row["source_id"] == representative["source_id"] and parent == representative_parent:
                    same_folder_count += 1
                quarantine_asset(db, run_id, asset_id, invalid_root, "exact_duplicate")
    db.connection.commit()
    result = StageResult(
        "exact_deduplication",
        StageStatus.WARNING if duplicate_count else StageStatus.PASS,
        f"Quarantined {duplicate_count} exact duplicate images; raw sources were preserved.",
        metrics={"duplicate_images": duplicate_count, "same_folder_duplicates": same_folder_count},
    )
    db.record_stage(run_id, result)
    return result


def difference_hash(image_path: Path, hash_size: int = 8) -> int:
    from PIL import Image

    with Image.open(image_path) as image:
        gray = image.convert("L").resize((hash_size + 1, hash_size))
        pixels = list(gray.get_flattened_data()) if hasattr(gray, "get_flattened_data") else list(gray.getdata())
    value = 0
    for row in range(hash_size):
        start = row * (hash_size + 1)
        for column in range(hash_size):
            value = (value << 1) | int(pixels[start + column] > pixels[start + column + 1])
    return value


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


class _BKNode:
    def __init__(self, value: int, row: object):
        self.value = value
        self.rows = [row]
        self.children: dict[int, _BKNode] = {}

    def add(self, value: int, row: object) -> None:
        distance = hamming_distance(self.value, value)
        if distance == 0:
            self.rows.append(row)
            return
        child = self.children.get(distance)
        if child is None:
            self.children[distance] = _BKNode(value, row)
        else:
            child.add(value, row)

    def query(self, value: int, radius: int) -> list[tuple[object, int]]:
        distance = hamming_distance(self.value, value)
        results = [(row, distance) for row in self.rows] if distance <= radius else []
        for edge, child in self.children.items():
            if distance - radius <= edge <= distance + radius:
                results.extend(child.query(value, radius))
        return results


def near_duplicates(
    db: PipelineDatabase,
    run_id: str,
    review_root: Path,
    automatic_distance: int,
    review_distance: int,
) -> StageResult:
    rows = db.rows(
        """SELECT asset_id, source_id, standard_image_path FROM assets
           WHERE run_id=? AND status='annotated' ORDER BY asset_id""",
        (run_id,),
    )
    hashes: list[tuple[object, int]] = []
    for row in rows:
        hashes.append((row, difference_hash(Path(str(row["standard_image_path"])))))

    candidates: list[tuple[object, object, int]] = []
    trees: dict[str, _BKNode] = {}
    hash_by_asset: dict[str, int] = {}
    row_by_asset: dict[str, object] = {}
    for row, value in hashes:
        source_id = str(row["source_id"])
        asset_id = str(row["asset_id"])
        hash_by_asset[asset_id] = value
        row_by_asset[asset_id] = row
        tree = trees.get(source_id)
        if tree is None:
            trees[source_id] = _BKNode(value, row)
            continue
        for previous, distance in tree.query(value, review_distance):
            candidates.append((previous, row, distance))
        tree.add(value, row)

    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    automatic = 0
    for left, right, distance in candidates:
        union(str(left["asset_id"]), str(right["asset_id"]))
        if distance <= automatic_distance:
            automatic += 1
    components: dict[str, list[str]] = defaultdict(list)
    for asset_id in parent:
        components[find(asset_id)].append(asset_id)

    involved: set[str] = set()
    for members in components.values():
        members.sort()
        representative = members[0]
        cluster_id = "near-" + hashlib.sha256(":".join(members).encode("ascii")).hexdigest()[:16]
        for asset_id in members:
            row = row_by_asset[asset_id]
            involved.add(asset_id)
            distance = hamming_distance(hash_by_asset[representative], hash_by_asset[asset_id])
            decision = "keep" if asset_id == representative else "pending_review"
            db.connection.execute(
                """INSERT OR REPLACE INTO duplicate_candidates
                   (run_id, cluster_id, asset_id, representative_asset_id, kind, distance, decision)
                   VALUES (?, ?, ?, ?, 'near', ?, ?)""",
                (run_id, cluster_id, asset_id, representative, distance, decision),
            )
            source_path = Path(str(row["standard_image_path"]))
            copy_or_link(source_path, review_root / cluster_id / f"{asset_id}{source_path.suffix}")
            if asset_id != representative:
                db.connection.execute(
                    """INSERT INTO reviews
                       (run_id, asset_id, review_type, decision, notes, external_task_id, created_at)
                       VALUES (?, ?, 'near_duplicate', 'pending', ?, ?, datetime('now'))""",
                    (run_id, asset_id, f"dHash distance to representative={distance}", cluster_id),
                )
        if distance <= automatic_distance:
            automatic += 1
    db.connection.commit()
    status = StageStatus.REVIEW_REQUIRED if components else StageStatus.PASS
    result = StageResult(
        "near_deduplication",
        status,
        f"Prepared {len(components)} suspected near-duplicate clusters for human review.",
        metrics={
            "candidate_pairs": len(candidates), "clusters": len(components),
            "assets_involved": len(involved), "high_confidence_pairs": automatic,
        },
    )
    db.record_stage(run_id, result)
    return result
