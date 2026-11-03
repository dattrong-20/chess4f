"""Immutable release publication across local Delta, S3, Spark and Trino.

One publisher at a time. A failed release never replaces the serving pointer.
Full snapshot exports are bounded-demo infrastructure, not incremental backfill.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from .config import data_root
from .storage import Lake, TABLES, atomic_json, utc_now

APPEND_ONLY = ("bronze/games", "silver/quarantine")


def _clone_tree(source, destination):
    """Reuse previous release files locally (hardlinks, copy as fallback)."""
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(path, target)
        except OSError:
            shutil.copy2(path, target)


def _partition_signatures(table_path):
    """Hash the active files of every year_month partition."""
    try:
        table = DeltaTable(str(table_path))
    except Exception:
        return None
    groups = {}
    for uri in table.file_uris():
        match = re.search(r"year_month=([^/\\]+)[/\\]", str(uri))
        if not match:
            return None
        path = Path(uri)
        groups.setdefault(match.group(1), []).append(f"{path.name}:{path.stat().st_size}")
    return {month: hashlib.sha1("\n".join(sorted(items)).encode()).hexdigest()
            for month, items in groups.items()}


def release_id(value):
    if not re.fullmatch(r"r_[0-9a-f]{32}", value):
        raise ValueError("Invalid release ID")
    return value


SPEEDS = ("blitz", "rapid", "bullet", "classical", "all")


def setup(project):
    path = Path(project) / ".env.lakehouse"
    # Never replace working credentials on a repeated setup.
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(f"CHESS4F_S3_USER=chess4f\nCHESS4F_S3_PASSWORD={secrets.token_hex(24)}\n")
    return {"configuration": str(path), "credentials": "generated locally; excluded from Git"}


def settings(project):
    result = {}
    for line in (Path(project) / ".env.lakehouse").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def client(project):
    import boto3
    from botocore.config import Config
    cfg = settings(project)
    return boto3.client("s3", endpoint_url=os.getenv("CHESS4F_S3_ENDPOINT", "http://127.0.0.1:19000"),
                        aws_access_key_id=cfg["CHESS4F_S3_USER"], aws_secret_access_key=cfg["CHESS4F_S3_PASSWORD"],
                        region_name="us-east-1", config=Config(s3={"addressing_style": "path"},
                        connect_timeout=10, read_timeout=60, retries={"max_attempts": 3}))


def snapshot(root):
    lake = Lake(root)
    rid = "r_" + uuid.uuid4().hex
    destination = Path(root) / "releases" / rid
    destination.mkdir(parents=True)
    pointer = Path(root) / "published/latest.json"
    previous = None
    previous_manifest = {}
    if pointer.exists():
        try:
            previous_manifest = json.loads(pointer.read_text(encoding="utf-8"))
            previous = previous_manifest.get("release_id")
        except ValueError:
            previous_manifest = {}
    previous_dir = Path(root) / "releases" / previous if previous else None
    manifest = {"release_id": rid, "created_at": utc_now(), "status": "preparing",
                "base_release": previous, "tables": {}, "partitions": {}}
    path = destination / "manifest.json"
    try:
        with lake.lock():
            manifest["source_versions"] = lake.versions()
            if not lake.exists("silver/games"):
                raise ValueError("Import games before exporting a release")
            with lake.connection() as con:
                for name in TABLES:
                    view = name.replace("/", "_")
                    count = con.execute(f"SELECT count(*) FROM {view}").fetchone()[0]
                    partitions = lake.partition_columns(name)
                    previous_table = previous_dir / name if previous_dir else None
                    exported = False
                    if previous_table and previous_table.exists() and partitions:
                        previous_partitions = DeltaTable(str(previous_table)).metadata().partition_columns
                        local_sig = _partition_signatures(lake.path(name))
                        previous_sig = previous_manifest.get("partitions", {}).get(name)
                        reusable = (list(previous_partitions) == partitions
                                    and isinstance(previous_sig, dict)
                                    and local_sig is not None)
                        if reusable:
                            _clone_tree(previous_table, destination / name)
                            for month in sorted(set(previous_sig) - set(local_sig)):
                                DeltaTable(str(destination / name)).delete(
                                    f"year_month = '{month}'")
                            changed = [month for month in sorted(local_sig)
                                       if previous_sig.get(month) != local_sig[month]]
                            for month in changed:
                                rows = con.execute(
                                    f"SELECT * FROM {view} WHERE year_month=?", [month]
                                ).to_arrow_reader(65536)
                                write_deltalake(str(destination / name), rows, mode="overwrite",
                                                predicate=f"year_month = '{month}'",
                                                partition_by=partitions)
                            manifest["partitions"][name] = local_sig
                            exported = True
                    elif previous_table and previous_table.exists() and name in APPEND_ONLY:
                        prev_ids = DeltaTable(str(previous_table)).to_pyarrow_table(
                            columns=["record_id"]).column("record_id").to_pylist()
                        con.register("previous_ids", pa.table(
                            {"record_id": pa.array(prev_ids, type=pa.string())}))
                        condition = "record_id NOT IN (SELECT record_id FROM previous_ids)"
                        new_count = con.execute(f"SELECT count(*) FROM {view} WHERE {condition}").fetchone()[0]
                        _clone_tree(previous_table, destination / name)
                        if new_count:
                            rows = con.execute(f"SELECT * FROM {view} WHERE {condition}").to_arrow_reader(65536)
                            write_deltalake(str(destination / name), rows, mode="append")
                        con.unregister("previous_ids")
                        exported = True
                    if not exported:
                        rows = con.execute(f"SELECT * FROM {view}").to_arrow_reader(65536)
                        write_deltalake(str(destination / name), rows, partition_by=partitions or None)
                        if partitions:
                            manifest["partitions"][name] = _partition_signatures(lake.path(name))
                    manifest["tables"][name] = {"rows": count, "snapshot_version": 0}
        manifest["status"] = "exported"
    except Exception as exc:
        manifest.update(status="failed", error=str(exc))
        raise
    finally:
        atomic_json(path, manifest)
    return manifest


def upload(root, project, rid):
    rid = release_id(rid)
    folder = Path(root) / "releases" / rid
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "exported":
        raise ValueError("Upload requires an exported, unpublished release")
    s3 = client(project)
    from botocore.exceptions import ClientError
    try:
        s3.head_bucket(Bucket="chess4f")
    except ClientError as exc:
        if str(exc.response["Error"]["Code"]) not in ("404", "NoSuchBucket"):
            raise
        s3.create_bucket(Bucket="chess4f")
    prefix = f"releases/{rid}/"
    # Refuse to overwrite a partial or complete release. Recovery uses a new ID.
    if s3.list_objects_v2(Bucket="chess4f", Prefix=prefix, MaxKeys=1).get("KeyCount", 0):
        raise ValueError("S3 release prefix already exists; export a new release for retry")
    previous = manifest.get("base_release")
    previous_prefix = f"releases/{previous}/" if previous else None
    active = []
    for name in TABLES:
        table_dir = folder / name
        if not table_dir.exists():
            continue
        for uri in DeltaTable(str(table_dir)).file_uris():
            path = Path(uri)
            active.append((path, f"{name}/{path.relative_to(table_dir).as_posix()}"))
        for log in sorted((table_dir / "_delta_log").glob("*")):
            if log.is_file():
                active.append((log, f"{name}/_delta_log/{log.name}"))
    copied = 0
    uploaded = 0
    for path, relative in sorted(active, key=lambda item: item[1]):
        key = prefix + relative
        source = (Path(root) / "releases" / previous / relative) if previous else None
        if source is not None and source.exists():
            s3.copy_object(Bucket="chess4f", Key=key,
                           CopySource={"Bucket": "chess4f", "Key": previous_prefix + relative})
            copied += 1
        else:
            s3.upload_file(str(path), "chess4f", key)
            uploaded += 1
    for path in sorted(p for p in (Path(root) / "bronze_objects").iterdir() if p.suffix in (".pgn", ".jsonl")):
        key = f"bronze_objects/{path.name}"
        try:
            s3.head_object(Bucket="chess4f", Key=key)
        except ClientError:
            s3.upload_file(str(path), "chess4f", key)
    manifest.update(status="uploaded", object_count=len(active), copied_objects=copied,
                    uploaded_objects=uploaded, uploaded_at=utc_now())
    s3.put_object(Bucket="chess4f", Key=prefix + "manifest.json", Body=json.dumps(manifest).encode())
    atomic_json(folder / "manifest.json", manifest)
    return manifest


def sql(statement, endpoint=None):
    endpoint = endpoint or os.getenv("CHESS4F_TRINO", "http://127.0.0.1:18090")
    rows, columns = [], []
    deadline = time.monotonic() + 180
    with httpx.Client(timeout=60, headers={"X-Trino-User": "chess4f"}) as http:
        response = http.post(endpoint + "/v1/statement", content=statement.encode())
        while True:
            response.raise_for_status()
            body = response.json()
            if body.get("error"):
                raise RuntimeError(body["error"].get("message", "Trino query failed"))
            columns = [col["name"] for col in body.get("columns", [])] or columns
            rows.extend(body.get("data", []))
            next_uri = body.get("nextUri")
            if not next_uri:
                return [dict(zip(columns, row)) for row in rows]
            if urlsplit(next_uri).netloc != urlsplit(endpoint).netloc:
                raise ValueError("Unexpected Trino result origin")
            if time.monotonic() > deadline:
                http.delete(next_uri)
                raise TimeoutError("Trino query exceeded 180 seconds")
            response = http.get(next_uri)


def register_tables(rid, locations):
    """Register missing Delta tables; tolerate an already-registered table.

    A partially registered schema or a retried publication can surface as a
    metastore duplicate-key error even after the preceding SHOW TABLES check.
    That is only accepted when the table is visible afterwards.
    """
    registered = {row["Table"] for row in sql(f"SHOW TABLES FROM chess.{rid}")}
    for table, location in locations.items():
        if table in registered:
            continue
        statement = (f"CALL chess.system.register_table(schema_name=>'{rid}', table_name=>'{table}', "
                     f"table_location=>'s3://chess4f/releases/{rid}/{location}')")
        try:
            sql(statement)
        except RuntimeError:
            if table not in {row["Table"] for row in sql(f"SHOW TABLES FROM chess.{rid}")}:
                raise


def validate_publish(root, project, rid):
    rid = release_id(rid)
    lake = Lake(root)
    with lake.lock():
        path = Path(root) / "releases" / rid / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["status"] not in ("uploaded", "published"):
            raise ValueError("Release must be uploaded first")
        sql(f"CREATE SCHEMA IF NOT EXISTS chess.{rid}")
        locations = {name.replace("/", "_"): name for name in TABLES}
        locations.update({"spark_openings": "spark/gold/openings", "spark_player_games": "spark/gold/player_games"})
        register_tables(rid, locations)
        results = {}
        for name, expected in manifest["tables"].items():
            count = sql(f"SELECT count(*) n FROM chess.{rid}.{name.replace('/', '_')}")[0]["n"]
            if count != expected["rows"]:
                raise ValueError(f"Trino source count mismatch: {name}")
            results[name] = count
        for name in ("openings", "player_games"):
            # Both directions preserve multiplicity and compare all columns.
            for left, right in [(f"gold_{name}", f"spark_{name}"), (f"spark_{name}", f"gold_{name}")]:
                mismatch = sql(f"SELECT count(*) n FROM (SELECT * FROM chess.{rid}.{left} "
                               f"EXCEPT ALL SELECT * FROM chess.{rid}.{right})")[0]["n"]
                if mismatch:
                    raise ValueError(f"Trino/Spark parity failed: {name}")
        manifest.update(status="published", verified_at=utc_now(), trino_counts=results,
                        parity="all columns and rows in both Gold tables", trino_schema=rid)
        s3 = client(project)
        body = json.dumps(manifest).encode()
        s3.put_object(Bucket="chess4f", Key=f"releases/{rid}/manifest.json", Body=body)
        # One-object pointer switch after all checks. Readers pin one release/request.
        s3.put_object(Bucket="chess4f", Key="published/latest.json", Body=body)
        atomic_json(path, manifest)
        atomic_json(Path(root) / "published/latest.json", manifest)
        return manifest


def overview(root, source, speed="blitz"):
    if source not in ("lichess", "chesscom", "import"):
        raise ValueError("Unknown source")
    if speed not in SPEEDS:
        raise ValueError("Unknown speed")
    pointer = Path(root) / "published/latest.json"
    if not pointer.exists():
        raise RuntimeError("No validated lakehouse release has been published")
    manifest = json.loads(pointer.read_text(encoding="utf-8"))
    rid = release_id(manifest["release_id"])
    speed_clause = "" if speed == "all" else f" AND speed='{speed}'"
    summary = sql(f"SELECT count(*) games, count(opening_family) recognized, "
                  f"count(DISTINCT opening_family) opening_families, min(played_at) first_game, "
                  f"max(played_at) last_game FROM chess.{rid}.silver_games "
                  f"WHERE source='{source}'{speed_clause}")[0]
    rows = sql(f"""SELECT opening_family, sum(n_games) n_games,
      100.0*sum(white_score_sum)/sum(n_games) white_score_pct,
      100.0*sum(white_wins)/sum(n_games) white_win_pct,
      100.0*sum(draws)/sum(n_games) draw_pct,
      100.0*sum(black_wins)/sum(n_games) black_win_pct,
      100.0*sum(n_games)/sum(sum(n_games)) OVER () popularity_pct
      FROM chess.{rid}.spark_openings WHERE source='{source}'{speed_clause}
      GROUP BY opening_family ORDER BY n_games DESC""")
    return {"summary": summary, "openings": rows, "source": source, "speed": speed,
            "engine": "trino", "release_id": rid, "versions": manifest["source_versions"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["setup", "snapshot", "upload", "publish"])
    p.add_argument("--release")
    p.add_argument("--project", type=Path, default=Path.cwd())
    args = p.parse_args()
    root = data_root()
    if args.action == "setup":
        result = setup(args.project)
    elif args.action == "snapshot":
        result = snapshot(root)
    elif not args.release:
        p.error("--release is required")
    elif args.action == "upload":
        result = upload(root, args.project, args.release)
    else:
        result = validate_publish(root, args.project, args.release)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
