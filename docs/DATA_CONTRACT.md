# Data contract and limitations

## Identity and time
- Game key: `platform:platform_game_id`. Lichess ID comes from Site; Chess.com ID from Link/API URL. Known-platform records without valid IDs are quarantined.
- Player key: platform + normalized username; same username across platforms is not merged.
- `played_at` is UTC start timestamp. Missing clock defaults to midnight: this resolution is insufficient for intraday leakage-sensitive comparisons and should be improved before general replay prediction.
- Games are complete only for results `1-0`, `0-1`, `1/2-1/2`. Nonstandard initial positions/variants are quarantined in v0.1.
- Invalid/missing Elo remains null; retained for player counts, excluded from model training and classified as unknown rating group.

## Tables
- `bronze/games`: parsed canonical PGN plus source, run and ingest timestamp; record hash distinguishes source payload versions.
- `bronze_objects/{sha256}.pgn`: exact imported PGN file. Public API JSON responses also retained under landing.
- `silver/games`: one current record per game key; derived month, Elo fields, score and opening label.
- `silver/moves`: one row per game key/ply, position before the move and FEN after it. Re-import replaces existing move rows for that game, including an obsolete tail.
- `silver/quarantine`: rejected record + reason + run; historical rejection records are audit evidence, not current invalid-game counts.
- `gold/openings`: recognized Rated Blitz by platform/month/rating group/family.
- `gold/player_games`: two perspective rows per completed game. Never count these rows as distinct global games.

## Opening rules
- Catalog downloaded at one Git commit, content hashed.
- Position key contains pieces, side to move, castling rights, legal en-passant; excludes clocks.
- Latest matching position within 36 plies; family is prefix before colon.
- A parent label does not automatically include all separately labelled children.
- Recognition coverage is not accuracy. Accuracy needs manual audited labels.

## Transaction and scale contract
- A file lock serializes pipeline writers on this local data root.
- Each Delta table write is transactional; a multi-table pipeline is not globally atomic.
- A failed run can leave newer Silver than Gold. Retry rebuilds Gold; run manifests expose failures. Coherent snapshot publication is a planned improvement.
- Gold currently rebuilds from Silver; it is correct at demo scale but not an incremental distributed aggregation.
- Tables are currently unpartitioned. DuckDB reads only active file URIs returned by the Delta transaction log, not an uncontrolled Parquet glob.
- Old Delta files remain for version recovery; no automatic vacuum is installed.

## Sample / coverage
- `limited` means intentionally stopped at a demo cap, never full source coverage.
- Selecting a day still reads the monthly compressed stream sequentially.
- Completing one source-file scan does not establish complete calendar-month coverage; UTC boundary games may be in adjacent sources.
- Do not mix a one-player history with a population sample for platform-wide findings.
