# Observed coverage ledger

`chess4f coverage [--source lichess|chesscom|import] [--write]` reads the local
Silver table and prints what was actually imported per source, month and day.
It exists because a single total ("103,511 games") hides *where inside a month*
those games came from.

This is an operational artifact, not a published Delta table and not a
Trino-served dataset. `--write` stores the JSON under `data/metadata/coverage.json`
(ignored by Git).

## Why it exists

A Lichess monthly archive is scanned sequentially and a demo cap keeps the
**first** matching games. The September sample can therefore be 1,000 games all
played on 1 September, which is not a monthly sample. Counting rows alone would
make that look like a normal month. The ledger reports `days_with_games`,
`first_day_games` and `last_day_games` so the shape of the sample is visible.

UTC timestamps also spill across month boundaries: a game played late on
31 August UTC can appear in the September source file. `boundary_risk` is the
sum of games on the first and last day of the imported month. It **flags** where
adjacent-file coverage would matter; it is not a count of missing games.

## Fields

| Field | Meaning |
|---|---|
| `source` | `lichess`, `chesscom` or `import`; sources are never pooled |
| `games` | distinct imported games in Silver (`game_key`) |
| `recognized` | games with a catalog opening label |
| `first_game`, `last_game` | first/last UTC day present |
| `unknown_rating` | games whose Elo fields could not be parsed |
| `rated_blitz` | games eligible for the opening aggregates |
| `days_with_games` | distinct UTC days observed inside the month |
| `first_day_games`, `last_day_games` | games on day 1 and on the month's last day |
| `boundary_risk` | `first_day_games + last_day_games` |
| `scan` | matching `metadata/refresh` and `metadata/months` checkpoint, if any |
| `scan.limited` | collection stopped at a cap; the month is not exhausted |

The checkpoints are joined by `(source, month)`. Only Lichess has refresh and
backfill checkpoints; other sources report `{"limited": false}` unless a
checkpoint exists.

## What the ledger does not prove

- It does not prove complete calendar-month or platform-wide coverage.
- It does not validate source archives; HTTP validators are not checksums.
- It does not add data. To widen coverage, raise the cap, import more months,
  or scan a full archive explicitly, then publish a new release.
- Adjacent-source UTC boundary backfill is still future work; the ledger only
  makes the exposure measurable.

## Checkpoint on 2026-11-03

| Source | Games | Month | Games | Days | First day | Last day | Scan |
|---|---:|---|---:|---:|---:|---:|---|
| lichess | 100,011 | 2026-01 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-02 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-03 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-04 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-05 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-06 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-07 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-08 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-09 | 10,000 | 1 | 10,000 | 0 | none |
| lichess | 100,011 | 2026-10 | 10,010 | 2 | 10,000 | 10 | none |
| lichess | 100,011 | 2026-11 | 1 | 1 | 0 | 0 | none |
| chesscom | 3,500 | 2026-03 | 295 | 17 | 6 | 0 | none |
| chesscom | 3,500 | 2026-04 | 177 | 15 | 0 | 0 | none |
| chesscom | 3,500 | 2026-05 | 488 | 17 | 0 | 0 | none |
| chesscom | 3,500 | 2026-06 | 709 | 24 | 0 | 29 | none |
| chesscom | 3,500 | 2026-07 | 588 | 22 | 41 | 47 | none |
| chesscom | 3,500 | 2026-08 | 548 | 21 | 100 | 0 | none |
| chesscom | 3,500 | 2026-09 | 601 | 21 | 0 | 4 | none |
| chesscom | 3,500 | 2026-10 | 94 | 15 | 0 | 0 | none |

Conclusions the project must keep stating:

1. The Lichess September sample is **single-day**, not a monthly sample.
2. Every Lichess monthly sample is a first-match cap concentrated on that
   month's first day; October adds 10 later player-sync games.
3. Chess.com now spans March-October 2026 because several accounts were synced;
   this is broader per-account history, still not a platform-wide sample.
4. Month-over-month opening comparisons remain illustrative, not population
   trends.
