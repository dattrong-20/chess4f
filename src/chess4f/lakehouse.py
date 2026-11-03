"""Immutable release publication across local Delta, S3, Spark and Trino.

One publisher at a time. A failed release never replaces the serving pointer.
Full snapshot exports are bounded-demo infrastructure, not incremental backfill.
"""
import argparse
import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from deltalake import write_deltalake

from .config import data_root
from .storage import Lake, TABLES, atomic_json, utc_now


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
    manifest = {"release_id": rid, "created_at": utc_now(), "status": "preparing", "tables": {}}
    path = destination / "manifest.json"
    try:
        with lake.lock():
            manifest["source_versions"] = lake.versions()
            if not lake.exists("silver/games"):
                raise ValueError("Import games before exporting a release")
            with lake.connection() as con:
                for name in TABLES:
                    count = con.execute(f"SELECT count(*) FROM {name.replace('/', '_')}").fetchone()[0]
                    table = con.execute(f"SELECT * FROM {name.replace('/', '_')}").to_arrow_reader(65536)
                    partitions = lake.partition_columns(name)
                    write_deltalake(str(destination / name), table, partition_by=partitions or None)
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
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "manifest.json")
    for path in files:
        s3.upload_file(str(path), "chess4f", prefix + path.relative_to(folder).as_posix())
    for path in sorted(p for p in (Path(root) / "bronze_objects").iterdir() if p.suffix in (".pgn", ".jsonl")):
        s3.upload_file(str(path), "chess4f", f"bronze_objects/{path.name}")
    manifest.update(status="uploaded", object_count=len(files), uploaded_at=utc_now())
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
