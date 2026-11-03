#!/usr/bin/env python3
"""One-way, source-authoritative clone of Drill/EI content tables.

Only the four content tables historically covered by sync_content are touched.
User attempts, state, markers, papers, accounts, passkeys, and timer data are
outside the scope of this utility. Target-only records are never deleted.
"""

from __future__ import annotations

import argparse
import datetime
import decimal
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import sql


@dataclass(frozen=True)
class Reference:
    column: str
    target_table: str
    target_key: str


@dataclass(frozen=True)
class ModelSpec:
    name: str
    table: str
    key_column: str
    references: tuple[Reference, ...] = ()
    binary_column: str | None = None


@dataclass(frozen=True)
class Record:
    key: str
    digest: str
    payload: dict[str, Any]


MODEL_SPECS = (
    ModelSpec("document", "drill_questiondocument", "source_id"),
    ModelSpec(
        "topic",
        "drill_questiontopic",
        "source_id",
        references=(
            Reference("document_id", "drill_questiondocument", "source_id"),
            Reference("parent_id", "drill_questiontopic", "source_id"),
        ),
    ),
    ModelSpec(
        "question",
        "drill_question",
        "uuid",
        references=(
            Reference("document_id", "drill_questiondocument", "source_id"),
            Reference("topic_id", "drill_questiontopic", "source_id"),
            Reference("similarity_topic_id", "drill_questiontopic", "source_id"),
        ),
    ),
    ModelSpec(
        "asset",
        "drill_questionasset",
        "source_id",
        references=(Reference("question_id", "drill_question", "uuid"),),
        binary_column="image_data",
    ),
)


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    if isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, memoryview):
        return bytes(value).hex()
    raise TypeError(f"Cannot canonicalize {type(value)!r}")


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        default=json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class Endpoint:
    def __init__(self, connection: psycopg.Connection):
        self.connection = connection
        self._columns: dict[str, tuple[str, ...]] = {}

    def columns(self, table: str) -> tuple[str, ...]:
        if table not in self._columns:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )
                self._columns[table] = tuple(row[0] for row in cursor.fetchall())
        return self._columns[table]

    def records(self, spec: ModelSpec) -> dict[str, Record]:
        omitted = {"id", *(ref.column for ref in spec.references)}
        if spec.binary_column:
            omitted.add(spec.binary_column)
        value_columns = [column for column in self.columns(spec.table) if column not in omitted]
        select_items = [sql.Identifier("base", column) for column in value_columns]
        for ref in spec.references:
            select_items.append(
                sql.SQL(
                    "(SELECT target.{target_key}::text FROM {target_table} target "
                    "WHERE target.id = base.{source_column}) AS {alias}"
                ).format(
                    target_key=sql.Identifier(ref.target_key),
                    target_table=sql.Identifier(ref.target_table),
                    source_column=sql.Identifier(ref.column),
                    alias=sql.Identifier(f"__ref__{ref.column}"),
                )
            )
        query = sql.SQL("SELECT {items} FROM {table} base ORDER BY base.{key}::text").format(
            items=sql.SQL(", ").join(select_items),
            table=sql.Identifier(spec.table),
            key=sql.Identifier(spec.key_column),
        )
        result: dict[str, Record] = {}
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            names = [item.name for item in cursor.description]
            for row in cursor:
                payload = dict(zip(names, row))
                key = str(payload[spec.key_column])
                result[key] = Record(key, canonical_hash(payload), payload)
        return result

    def blob(self, spec: ModelSpec, key: str) -> bytes:
        query = sql.SQL("SELECT {binary} FROM {table} WHERE {key}::text = %s").format(
            binary=sql.Identifier(spec.binary_column),
            table=sql.Identifier(spec.table),
            key=sql.Identifier(spec.key_column),
        )
        with self.connection.cursor() as cursor:
            cursor.execute(query, (key,))
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Missing source {spec.name} {key}")
        return bytes(row[0])

    def resolve_references(self, spec: ModelSpec, payload: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        with self.connection.cursor() as cursor:
            for ref in spec.references:
                ref_key = payload[f"__ref__{ref.column}"]
                if ref_key is None:
                    resolved[ref.column] = None
                    continue
                query = sql.SQL("SELECT id FROM {table} WHERE {key}::text = %s").format(
                    table=sql.Identifier(ref.target_table),
                    key=sql.Identifier(ref.target_key),
                )
                cursor.execute(query, (ref_key,))
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        f"Missing target reference {ref.target_table}.{ref.target_key}={ref_key}"
                    )
                resolved[ref.column] = row[0]
        return resolved

    def upsert(self, spec: ModelSpec, record: Record, source: "Endpoint") -> tuple[int, int]:
        values = {key: value for key, value in record.payload.items() if not key.startswith("__ref__")}
        values.update(self.resolve_references(spec, record.payload))
        asset_count = 0
        asset_bytes = 0
        if spec.binary_column:
            blob = source.blob(spec, record.key)
            actual_hash = hashlib.sha256(blob).hexdigest()
            expected_hash = str(record.payload.get("sha256", "")).lower()
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Asset {record.key} failed SHA-256 verification: expected {expected_hash}, got {actual_hash}"
                )
            values[spec.binary_column] = blob
            asset_count = 1
            asset_bytes = len(blob)
        columns = list(values)
        assignments = [column for column in columns if column != spec.key_column]
        query = sql.SQL(
            "INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            "ON CONFLICT ({key}) DO UPDATE SET {assignments}"
        ).format(
            table=sql.Identifier(spec.table),
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
            placeholders=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            key=sql.Identifier(spec.key_column),
            assignments=sql.SQL(", ").join(
                sql.SQL("{column} = EXCLUDED.{column}").format(column=sql.Identifier(column))
                for column in assignments
            ),
        )
        with self.connection.cursor() as cursor:
            cursor.execute(query, [values[column] for column in columns])
        return asset_count, asset_bytes


def connect(url: str, *, read_only: bool) -> psycopg.Connection:
    connection = psycopg.connect(url, connect_timeout=10)
    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    connection.execute("SET TIME ZONE 'UTC'")
    connection.execute("SET lock_timeout = '15s'")
    connection.execute("SET statement_timeout = '45min'")
    if read_only:
        connection.execute("SET TRANSACTION READ ONLY")
    return connection


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    source_url = os.environ["SOURCE_DATABASE_URL"]
    target_url = os.environ["DATABASE_URL"]
    if source_url == target_url:
        raise RuntimeError("Source and target database URLs must differ")

    report: dict[str, Any] = {"mode": "apply" if options.apply else "dry-run", "models": {}}
    source_connection = connect(source_url, read_only=True)
    target_connection = connect(target_url, read_only=not options.apply)
    source = Endpoint(source_connection)
    target = Endpoint(target_connection)
    try:
        source_connection.execute("SELECT pg_advisory_xact_lock(hashtext('time_tracker_nuc_content_clone_v1'))")
        target_connection.execute("SELECT pg_advisory_xact_lock(hashtext('time_tracker_nuc_content_clone_v1'))")
        for spec in MODEL_SPECS:
            if source.columns(spec.table) != target.columns(spec.table):
                raise RuntimeError(f"Column mismatch for {spec.table}")
            source_records = source.records(spec)
            target_records = target.records(spec)
            changed = [
                record
                for key, record in source_records.items()
                if key not in target_records or target_records[key].digest != record.digest
            ]
            target_only = sorted(set(target_records) - set(source_records))
            model_report = {
                "source": len(source_records),
                "target_before": len(target_records),
                "changed_or_missing": len(changed),
                "target_only_preserved": len(target_only),
                "assets_transferred": 0,
                "asset_bytes_transferred": 0,
            }
            if options.apply:
                for record in changed:
                    assets, asset_bytes = target.upsert(spec, record, source)
                    model_report["assets_transferred"] += assets
                    model_report["asset_bytes_transferred"] += asset_bytes
                target_after = target.records(spec)
                mismatches = [
                    key
                    for key, record in source_records.items()
                    if key not in target_after or target_after[key].digest != record.digest
                ]
                if mismatches:
                    diagnostics = []
                    for key in mismatches[:3]:
                        source_payload = source_records[key].payload
                        target_payload = target_after.get(key)
                        if target_payload is None:
                            diagnostics.append({"key": key, "missing": True})
                            continue
                        differing_fields = [
                            field
                            for field in sorted(set(source_payload) | set(target_payload.payload))
                            if source_payload.get(field) != target_payload.payload.get(field)
                        ]
                        diagnostics.append({"key": key, "fields": differing_fields})
                    raise RuntimeError(
                        f"Post-clone verification failed for {spec.table}: "
                        f"{len(mismatches)} mismatches; diagnostics={diagnostics}"
                    )
                model_report["verified_source_records"] = len(source_records)
            report["models"][spec.name] = model_report
        if options.apply:
            target_connection.commit()
        else:
            target_connection.rollback()
        source_connection.rollback()
    except Exception:
        target_connection.rollback()
        source_connection.rollback()
        raise
    finally:
        target_connection.close()
        source_connection.close()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
