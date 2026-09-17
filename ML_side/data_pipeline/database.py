from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import StageResult


SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineDatabase:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "PipelineDatabase":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection:
            yield self.connection

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                seed INTEGER NOT NULL,
                git_sha TEXT,
                git_dirty INTEGER,
                code_sha256 TEXT NOT NULL DEFAULT '',
                config_path TEXT NOT NULL,
                config_sha256 TEXT NOT NULL,
                download_sheet_path TEXT,
                download_sheet_sha256 TEXT,
                runtime_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sources (
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                source_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                source_version TEXT,
                source_url TEXT NOT NULL,
                licence TEXT NOT NULL,
                licence_url TEXT NOT NULL DEFAULT '',
                governance_status TEXT NOT NULL DEFAULT 'review_required',
                raw_folder TEXT NOT NULL,
                annotation_format TEXT NOT NULL,
                environment_tags_json TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (run_id, source_id)
            );
            CREATE TABLE IF NOT EXISTS assets (
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                asset_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                parent_asset_id TEXT,
                original_filename TEXT NOT NULL,
                original_relative_path TEXT NOT NULL,
                raw_image_path TEXT NOT NULL,
                raw_label_path TEXT,
                standard_image_path TEXT,
                standard_label_path TEXT,
                original_sha256 TEXT NOT NULL,
                current_sha256 TEXT,
                original_width INTEGER,
                original_height INTEGER,
                width INTEGER,
                height INTEGER,
                image_format TEXT,
                exif_orientation INTEGER,
                group_id TEXT,
                split TEXT,
                status TEXT NOT NULL,
                quarantine_reason TEXT,
                environment_tags_json TEXT NOT NULL,
                is_augmented INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                PRIMARY KEY (run_id, asset_id),
                FOREIGN KEY (run_id, source_id) REFERENCES sources(run_id, source_id)
            );
            CREATE TABLE IF NOT EXISTS annotations (
                annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                source_class_id INTEGER NOT NULL,
                target_class_id INTEGER,
                x_center REAL NOT NULL,
                y_center REAL NOT NULL,
                width REAL NOT NULL,
                height REAL NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (run_id, asset_id) REFERENCES assets(run_id, asset_id)
            );
            CREATE TABLE IF NOT EXISTS transformations (
                transformation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                operation TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                input_sha256 TEXT,
                output_sha256 TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id, asset_id) REFERENCES assets(run_id, asset_id)
            );
            CREATE TABLE IF NOT EXISTS stage_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                source_id TEXT,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS duplicate_candidates (
                run_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                representative_asset_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                distance INTEGER NOT NULL,
                decision TEXT NOT NULL,
                PRIMARY KEY (run_id, cluster_id, asset_id),
                FOREIGN KEY (run_id, asset_id) REFERENCES assets(run_id, asset_id)
            );
            CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                asset_id TEXT,
                review_type TEXT NOT NULL,
                reviewer TEXT,
                decision TEXT NOT NULL,
                notes TEXT NOT NULL,
                findings_json TEXT NOT NULL DEFAULT '{}',
                external_task_id TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(run_id, status);
            CREATE INDEX IF NOT EXISTS idx_assets_source ON assets(run_id, source_id);
            CREATE INDEX IF NOT EXISTS idx_annotations_asset ON annotations(run_id, asset_id);
            """
        )
        self._ensure_column("sources", "source_version", "TEXT")
        self._ensure_column("sources", "licence_url", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("sources", "governance_status", "TEXT NOT NULL DEFAULT 'review_required'")
        self._ensure_column("assets", "original_width", "INTEGER")
        self._ensure_column("assets", "original_height", "INTEGER")
        self._ensure_column("reviews", "findings_json", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("runs", "git_dirty", "INTEGER")
        self._ensure_column("runs", "code_sha256", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("runs", "download_sheet_path", "TEXT")
        self._ensure_column("runs", "download_sheet_sha256", "TEXT")
        self.connection.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.connection.commit()

    def _ensure_column(self, table: str, column: str, declaration: str) -> None:
        existing = {str(row[1]) for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def record_stage(self, run_id: str, result: StageResult) -> None:
        self.connection.execute(
            """INSERT INTO stage_results
               (run_id, source_id, stage, status, message, metrics_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                result.source_id,
                result.stage,
                result.status.value,
                result.message,
                json.dumps(result.metrics, sort_keys=True),
                utc_now(),
            ),
        )
        self.connection.commit()

    def add_transform(
        self,
        run_id: str,
        asset_id: str,
        stage: str,
        operation: str,
        parameters: dict[str, Any],
        input_sha256: str | None,
        output_sha256: str | None,
    ) -> None:
        self.connection.execute(
            """INSERT INTO transformations
               (run_id, asset_id, stage, operation, parameters_json, input_sha256, output_sha256, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, asset_id, stage, operation, json.dumps(parameters, sort_keys=True), input_sha256, output_sha256, utc_now()),
        )
        self.connection.commit()

    def rows(self, query: str, parameters: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(query, parameters))
