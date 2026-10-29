import argparse
import json
from pathlib import Path

from .analytics import overview
from .config import data_root
from .live import observe
from .openings import download_catalog
from .pipeline import ingest_pgn
from .sources import chesscom_archive, lichess_day, month_plan


def main():
    parser = argparse.ArgumentParser(prog="chess4f")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog", help="Fetch opening reference at one immutable Git commit")
    sub.add_parser("status", help="Counts and committed Delta versions")
    p = sub.add_parser("ingest")
    p.add_argument("path", type=Path)
    p.add_argument("--source", choices=["lichess", "chesscom", "import"], default="import")
    p.add_argument("--start"); p.add_argument("--end")
    p.add_argument("--limit", type=int)
    p = sub.add_parser("sync-player")
    p.add_argument("username"); p.add_argument("--month", required=True)
    p = sub.add_parser("fetch-day")
    p.add_argument("day")
    p.add_argument("--limit", type=int, default=1000, help="First matching games for integration demo, not representative sampling")
    p.add_argument("--all", action="store_true", help="Scan entire monthly source; potentially large network/time cost")
    p = sub.add_parser("plan")
    p.add_argument("--start", required=True); p.add_argument("--end")
    p = sub.add_parser("live")
    p.add_argument("game_id"); p.add_argument("--max-events", type=int)
    p = sub.add_parser("train")
    p.add_argument("--source", required=True, choices=["lichess","chesscom"])
    p.add_argument("--speed", default="blitz")
    p = sub.add_parser("sync-months")
    p.add_argument("--start",required=True); p.add_argument("--end")
    p.add_argument("--limit",type=int,default=1000); p.add_argument("--all",action="store_true")
    p.add_argument("--force",action="store_true")
    args = parser.parse_args()
    root = data_root()
    if args.command == "catalog":
        result = download_catalog(root)
    elif args.command == "ingest":
        result = ingest_pgn(root, args.path, args.source, args.start, args.end, args.limit)
    elif args.command == "sync-player":
        path, uri = chesscom_archive(root, args.username, args.month)
        result = ingest_pgn(root, path, "chesscom", source_uri=uri)
    elif args.command == "fetch-day":
        path, uri, source_report = lichess_day(root, args.day, None if args.all else args.limit)
        result = ingest_pgn(root, path, "lichess", start=args.day, end=args.day, source_uri=uri)
        result["source_selection"] = source_report
    elif args.command == "plan":
        result = {"months": month_plan(args.start, args.end), "note": "Plan only. Availability must be checked at source."}
    elif args.command == "live":
        result = observe(root, args.game_id, args.max_events)
    elif args.command == "train":
        from .model import train
        result = train(root,args.source,args.speed)
    elif args.command == "sync-months":
        from .orchestrator import sync_months
        result = sync_months(root,args.start,args.end,None if args.all else args.limit,args.force)
    else:
        result = overview(root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
