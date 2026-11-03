# CV material — verified 2026-11-03

Repository: https://github.com/dattrong-20/chess4f
Use only the claims below; the **Do not claim** section is part of the material.

## One line

Built a traceable chess analytics lakehouse: public PGN ingestion, opening
recognition, Delta Bronze/Silver/Gold tables, immutable S3 releases validated by
Spark and Trino, and a FastAPI/Streamlit application with Dagster orchestration.

## Stack

Python 3.11 · Delta Lake (delta-rs) · DuckDB · PyArrow · MinIO S3 · Apache Spark 3.5
· Apache Hive Metastore 4 · Trino 484 · Dagster 1.13 · FastAPI · Streamlit · Plotly
· Docker Compose · pytest · GitHub Actions

## English bullets

- Built an end-to-end chess data platform ingesting public Lichess and Chess.com
  games into Bronze/Silver/Gold Delta tables: 5,498 games and 440,517 move rows,
  with content-addressed source objects (SHA-256), stable platform game IDs,
  idempotent upserts, quarantine and run manifests.
- Implemented immutable release publication: snapshot under a writer lock,
  upload to S3-compatible storage, independent Spark `local[2]` recomputation,
  bidirectional row/multiset parity against local Gold, Trino registration and
  count validation, then a single serving-pointer switch; a failed validation
  leaves the previous release serving.
- Served analytics through Trino only, with the release ID pinned once per
  request, parameterised SQL literals, and no silent DuckDB fallback (HTTP 503
  when the published lakehouse is unavailable).
- Orchestrated collection with Dagster: daily HEAD-only source checks, a capped
  weekly refresh, and a durable request queue for player-history sync, monthly
  backfill and finished live games, with per-month progress and retry from the UI.
- Added an observed-coverage ledger that reports games per source/month/day and
  UTC boundary exposure, so sample shape is documented instead of implied by a
  total.
- Wrote 44 pytest tests covering repeat-ingest idempotency, quarantine,
  correction of obsolete move tails, temporal leakage cutoffs, SQL literal
  binding, release pinning, parity-failure pointer preservation, and queue
  retry semantics.

## Vietnamese bullets

- Xây dựng nền tảng phân tích cờ vua end-to-end: ingest PGN công khai vào Delta
  Bronze/Silver/Gold (2.530 ván, 186.383 dòng nước đi), ID ván ổn định, upsert
  idempotent, quarantine và run manifest.
- Thiết kế publish release bất biến: snapshot → MinIO S3 → Spark tính lại Gold →
  đối chiếu parity hai chiều → Trino xác thực → chuyển con trỏ serving; lỗi không
  làm mất bản đang phục vụ.
- Phục vụ analytics chỉ qua Trino, pin release theo từng request, không fallback
  DuckDB ngầm; lỗi hạ tầng trả 503 thay vì số liệu cũ/sai.
- Điều phối bằng Dagster: kiểm tra nguồn hằng ngày, refresh có giới hạn hằng
  tuần, hàng đợi bền cho đồng bộ lịch sử người chơi/backfill/ván live, có tiến độ
  và retry theo tháng.
- Thêm coverage ledger báo số ván theo nguồn/tháng/ngày và rủi ro biên UTC, buộc
  phạm vi mẫu phải minh bạch thay vì suy ra từ tổng số.
- 44 test pytest cho idempotency, quarantine, sửa đuôi nước đi cũ, chặn rò rỉ
  tương lai, bind SQL, pin release, giữ nguyên pointer khi parity lỗi.

## Evidence

| Claim | Evidence |
|---|---|
| 5,498 games / 440,517 moves | published release manifest `data/published/latest.json` |
| Spark + Trino parity before publish | `lakehouse.validate_publish`, `jobs/build_gold.py`, docs/LAKEHOUSE.md |
| Trino-only serving, 503 on failure | `src/chess4f/trino_serving.py`, `tests/test_serving.py` |
| Dagster jobs/schedules/queue | `src/chess4f/definitions.py`, docs/ORCHESTRATION.md |
| Coverage ledger | `src/chess4f/coverage.py`, docs/COVERAGE.md |
| Test count | `pytest -q` → 44 passed |
| Real UI screenshots | `docs/images/*.png` captured with Playwright, embedded in README |

## Do not claim

- A multi-node Spark cluster; it is one local driver (`local[2]`).
- Representative monthly or platform-wide data; samples are bounded and the
  September Lichess sample is a single day.
- Public-user authentication or internet-safe write endpoints; the API is
  localhost-only.
- A chess engine, move recommendation, or validated live win prediction.
- Production high availability; Dagster uses local SQLite on one machine.
