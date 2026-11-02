# Source refresh

`chess4f refresh-months --start 2026-09 --check-only` checks monthly source availability through the previous calendar month. It reads HTTP headers only, never assumes a calendar month is already published, and records observations under `data/metadata/refresh`.

To ingest a bounded demo, omit `--check-only` and optionally set `--end YYYY-MM --limit 1000`. This selects the first matching Rated Blitz games in each source file, not a representative sample. `--all` scans the whole monthly file and can require substantial time/network/disk. It still does not guarantee UTC boundary coverage from adjacent files.

Successful scope/revision checkpoints allow later runs to skip an unchanged HTTP validator with the same limit. A changed limit or source revision triggers ingestion. Missing validators never enable skipping. A failed attempt preserves the previous successful revision. A source change detected between HEAD checks surrounding download is rejected before ingestion. HTTP validators are not cryptographic archive checksums.

The refresh lock prevents simultaneous refresh runners. Pipeline ingestion retains stable-ID upsert semantics; it does not delete old games omitted from a revised archive. Collection updates local Delta data only. Publish a new Spark/Trino release with `scripts/run-lakehouse.ps1` before expecting the default dashboard to display it.

This command is suitable for an external scheduler, but no recurring job has been installed or enabled yet. Existing `sync-months` remains the explicit sequential backfill command; `refresh-months` is the revision-aware entry point.

Verified on 2026-11-02: HEAD probes for September and October 2026 returned available archives with ETag, Last-Modified and Content-Length. The check-only run did not download or import either archive. Automated tests cover revision/scope changes, check-only behavior, absent sources, ingestion failure and changes during download.