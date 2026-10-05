# Opt-In Bulk Backfill Import

## Status

Implemented

## Objective

Add an explicitly opt-in historical backfill mode for large wide CSV imports. The mode must
load data into an import-scoped shadow destination, deduplicate and validate it before touching
the live `measurements` table, build shadow indexes once, and merge data through a resumable,
rollback-aware boundary.

The first implementation targets the disposable Inter-IFL historical file: approximately
164,680 source rows, 776 sensor columns, and 1.29 GiB on disk. It must remain disabled by
default and must not change the normal upload path.

## User need

The existing async bulk importer is correct and resumable, but it inserts each chunk directly
into the live `measurements` table. Develop already contains approximately 64 million
measurements, 7.3 GiB of table storage, and 6.4 GiB of indexes. A prior full-file attempt
reached approximately 8.91 GiB of a 10 GiB Postgres cgroup limit after 34,000 rows.

The user needs a controlled path for a large historical backfill that can be inspected,
validated, paused, retried, and rolled back without exposing partially accepted data as a
successful import or corrupting unrelated measurements.

## Current code/system summary

- `UploadImport` and `UploadImportChunk` provide durable manifests, leases, chunk hashes,
  progress counts, and resumable worker processing.
- `process_measurements_file_bulk()` already parses bounded CSV rows, stores sensor values as
  JSONB, performs set-based unpivoting, applies deterministic first-source-row-wins behavior,
  and inserts directly into `measurements` with `ON CONFLICT (sensorid, collectiontime) DO NOTHING`.
- Redundant measurement indexes were removed, geometry/statistics work was moved after chunk
  ingestion, and the deployed worker runs both phases with `--poll-all`.
- `UploadFileEvent.upload_session_id` is set to the import UUID, so inserted measurements can
  be identified for an import-scoped rollback without adding a user-controlled deletion filter.
- The live `measurements` table is not partitioned. A true PostgreSQL partition attach is
  therefore not available in the first implementation without a larger schema migration.

## Proposed design

### Opt-in contract

1. Add `ingestion_mode: Literal["standard", "backfill"]` to `UploadImportCreate`, defaulting
   to `standard` for compatibility.
2. Add a separate `BULK_BACKFILL_ENABLED` feature flag, default `false`. Backfill requests
   require this flag plus the existing async bulk flags.
3. Enforce a separate backfill byte admission limit and keep production admission behind an
   explicit feature flag and develop benchmark gate. The current API cannot reliably observe
   free space on the Postgres volume, so database-volume acceptance remains operator-controlled.
4. Expose the selected mode and backfill phase in the import status response. The existing
   standard mode keeps its current state machine and SQL path.

The backfill mode is stored on the durable import record at creation time; it cannot change
after the first chunk is accepted. No legacy single-request upload may select this mode.

### Durable backfill state

Add a one-to-one `upload_import_backfills` table keyed by `upload_imports.id` with:

- server-generated raw/shadow table names;
- phase: `staging`, `materializing`, `validating`, `ready`, `merging`, `merged`, `failed`, or
  `rolled_back`;
- staged-row/value counts and merged-value counts;
- validation timestamp and merge/rollback timestamps;
- lease token/expiry for materialization and merge;
- bounded error text and cleanup state.

Table names are generated only from the import UUID. They are never accepted from the client,
and SQL identifiers are quoted or constructed through a narrowly validated helper.

### Stage and shadow tables

1. During chunk processing, write one durable raw JSONB row per source CSV row into an
   import-scoped raw table. The raw table has no per-value unique index; it retains the source
   chunk index, row ordinal within that chunk, collection time, coordinates, and the validated
   sensor-id/value object. Chunks are required to preserve source-file order; the deterministic
   source order is `(chunk_index, row_ordinal)`, so out-of-order chunk arrival cannot change
   first-source-row-wins behavior. Raw rows are keyed by `(chunk_index, row_ordinal)` so a
   worker retry cannot duplicate a partially staged chunk.
2. After all chunks are sealed and processed, materialize a second import-scoped shadow table
   of long-form measurement rows with a set-based SQL operation.
3. Apply deterministic first-source-row-wins deduplication during materialization.
4. Build the shadow unique index on `(sensorid, collectiontime)` once after materialization.
5. Validate counts, sensor ownership, time/coordinate bounds, duplicate counts, and target
   collision counts before any merge into `measurements`.
6. Drop the raw table only after the shadow table is validated and durable. Retain the shadow
   table through merge completion or explicit rollback according to the configured retention
   policy.

The shadow table is logged rather than `UNLOGGED` in the first implementation so a worker or
Postgres restart does not silently erase the only validated copy. A later benchmark may permit
an unlogged raw table only if restart recovery can deterministically rebuild it from acknowledged
chunks.

### Merge and rollback

1. Acquire a per-station database/advisory lock and a row lease on the backfill state.
2. Use the same station lock for every standard-mode live-table write transaction. This makes
   the concurrency rule shared by both paths: unrelated stations remain independent, while
   same-station writes serialize at the target-table boundary. The lock is held per bounded
   transaction, not for the entire staging/validation lifetime.
3. Merge the validated shadow rows into `measurements` in bounded transactions using the
   existing unique conflict rule. Record progress after each committed batch.
4. Keep the import's upload-event identity on inserted rows. A rollback deletes only rows whose
   `upload_file_events.upload_session_id` equals this import UUID and whose station matches the
   import; it never uses a broad station/time predicate.
5. If staging, materialization, or validation fails, drop only this import's tables and mark the
   backfill failed. If merge fails partway through, pause in `merging` and require an explicit
   rollback or resume decision; do not automatically delete live rows. The first implementation
   permits explicit import-scoped rollback while the backfill is `ready`, `merging`, or `merged`
   and post-processing has not started; after post-processing begins, rollback is an operator
   decision outside this workflow.
6. Run statistics and station geometry only after merge validation succeeds. A post-processing
   failure is retried independently and does not trigger an implicit data rollback.

The first implementation does not claim to support partition attach. A later partitioned
measurements design may replace the bounded merge with a validated partition attach after the
partitioning, key, foreign-key, and query changes are separately approved.

## Files likely affected

- `upstream-docker-pods/app/api/v1/schemas/upload_import.py` — mode and backfill status fields.
- `upstream-docker-pods/app/api/v1/routes/upload_file/upload_imports.py` — opt-in validation,
  mode selection, status serialization, and backfill lifecycle endpoints/guards.
- `upstream-docker-pods/app/db/models/upload_import.py` — relationship to backfill state.
- `upstream-docker-pods/app/db/models/upload_import_backfill.py` — new durable backfill state.
- `upstream-docker-pods/app/services/upload_import_service.py` — phase claims, leases,
  validation, merge progress, and import-scoped rollback.
- `upstream-docker-pods/app/services/upload_import_backfill_service.py` — shadow-table DDL,
  materialization, validation, merge, and cleanup helpers.
- `upstream-docker-pods/app/workers/process_upload_imports.py` — dispatch standard versus
  backfill phases while retaining one-import-at-a-time behavior.
- `upstream-docker-pods/app/utils/bulk_upload_csv.py` — reusable bounded parsing/staging helpers
  without changing standard-mode semantics.
- `upstream-docker-pods/alembic/versions/` — additive backfill state migration only.
- `upstream-docker-pods/tests/` — state-machine, SQL, rollback, concurrency, and API tests.
- `upstream-sdk/` and generated API models — optional mode/status support for the client path.
- `upstream-docker-pods/README.md` — opt-in configuration and operator runbook.
- `docs/design/2026-09-30-wide-csv-bulk-ingestion.md` — link this design and record final
  implementation decisions.

## API/schema changes

- `POST /api/v1/campaigns/{campaign_id}/stations/{station_id}/imports` gains an optional
  `ingestion_mode` field with a compatibility-preserving default of `standard`.
- `GET /api/v1/imports/{import_id}` reports the mode, backfill phase, staged/merged counts,
  validation state, and rollback state.
- The existing `UploadImport` table gains a one-to-one relationship to additive backfill state;
  existing rows default to standard mode with no backfill record.
- No existing measurement columns or uniqueness semantics change in this phase.
- No CKAN API, Tapis token, or production data mutation is added to the worker.

## Data flow

```text
SDK --mode=backfill--> API
                         |
                         v
                  shared import volume
                         |
                         v
                 raw shadow table (JSONB)
                         |
                         v
              deduplicated shadow measurements
                         |
                    validate + index
                         |
              station lock + bounded merge
                         v
                   live measurements
                         |
                  stats + geometry phase
```

The API owns authentication, manifest validation, chunk hashing, and file persistence. The
worker owns shadow materialization, validation, merge leases, and cleanup. The live table is
untouched until the shadow state reaches `ready`.

Validation counts are a pre-merge snapshot. The merge remains authoritative and uses the live
unique constraint, so a concurrent same-station write may turn a validated candidate into a
target conflict without violating correctness.

## Risks and tradeoffs

- A shadow table improves validation and rollback but temporarily requires additional disk for
  raw and long-form data. Storage headroom must be measured before staging begins.
- The API must perform a conservative preflight using configured maximum shadow expansion and
  available database-volume headroom; if the deployment cannot expose reliable free-space
  information, backfill admission remains an operator-gated develop-only action rather than an
  automatic production decision.
- The final merge still grows the live table and its unique index. This design controls the
  failure boundary; it does not guarantee that the current unpartitioned table can absorb the
  entire historical file within the current resource limits.
- Dynamic per-import table creation introduces DDL, cleanup, and identifier-safety complexity.
- A worker crash during merge can leave committed live rows; import-event-scoped rollback and
  idempotent resume are mandatory.
- Per-station serialization protects correctness but may delay normal uploads to that station.
- A future partition-attach path could reduce merge pressure, but partitioning the existing
  table has primary-key, foreign-key, query, and migration consequences.
- Raw/shadow tables can expose sensitive measurements inside the database; access remains under
  the existing database credentials and names are unguessable UUID-derived identifiers.

## Alternatives considered

- **Repeat the current JSONB/upsert optimization:** rejected because it is already implemented
  and the remaining pressure is live table/index/WAL growth.
- **Use anti-join instead of `ON CONFLICT` only:** useful for duplicate-heavy retries but not
  sufficient for the mostly-new historical backfill.
- **Blindly raise Postgres memory:** rejected because it does not reduce table/index/WAL growth
  or establish storage headroom.
- **Drop the live unique index during import:** rejected for the first phase because it weakens
  concurrent-import correctness and makes rollback/recovery unsafe.
- **Convert the existing measurements table to partitions now:** deferred because it is a
  separate schema migration with key/foreign-key/query implications.
- **Client-side long-form conversion:** rejected because it multiplies transfer volume and
  moves the bottleneck to the client.

## Test plan

1. Unit-test mode gating, default standard behavior, state transitions, lease expiry, and
   server-generated identifier validation.
2. Use a PostgreSQL fixture to test raw staging, deterministic duplicate selection, shadow index
   creation, target collision counts, and bounded merge progress.
3. Test worker restart at staging, materialization, validation, and merge boundaries.
4. Test rollback before merge and after partial merge; verify unrelated station/import rows are
   unchanged.
5. Test concurrent same-station backfills and standard uploads; target writes must serialize on
   the shared station lock, never interleave unsafely.
6. Run a bounded real-data develop benchmark and record rows/values per second, table/index
   growth, WAL bytes, cgroup memory, staging disk, restart behavior, and final counts.
7. Pass criteria: no duplicate keys, deterministic counts, no unrelated-row changes, resumable
   leases, import-scoped cleanup, and no OOM or uncontrolled storage growth.

## Documentation plan

- Document the opt-in flag, request mode, lifecycle, storage headroom check, same-station
  serialization, rollback commands, and retention policy in `upstream-docker-pods/README.md`.
- Update the service API documentation for the new request/status fields after the schema is
  implemented.
- Update the DSO Architecture Upstream service page if the API contract or deployment settings
  change; the architecture repo is outside this workspace and must be updated separately.

## Rollout/rollback plan

1. Add the migration and code with `BULK_BACKFILL_ENABLED=false` everywhere.
2. Run local PostgreSQL tests and static checks.
3. Deploy the immutable image to develop with backfill disabled; verify standard async imports
   remain unchanged.
4. Enable backfill only for a disposable develop campaign/station and a bounded real-data slice.
5. If validation fails, stop the worker, drop only the import-scoped raw/shadow tables, and leave
   `measurements` untouched.
6. If merge partially completes, use the import UUID/event scope to roll back or resume after
   operator review; do not downgrade the migration while a backfill is active.
7. Production remains disabled until the bounded benchmark and rollback tests pass and a separate
   production approval is recorded.

## Open questions

- What minimum free database-volume and staging-volume headroom is required before accepting a
  backfill? The current database is approximately 13 GiB before this file is added.
- The first implementation will support operator-triggered import-scoped rollback after a
  successful merge only while post-processing has not started; rollback after that boundary is
  explicitly out of scope.
- Should the shadow table retain full geometry/metadata columns or only the fields needed by the
  current measurements insert?
- Is a bounded merge into the current table acceptable for the historical file, or is a future
  partitioned measurements migration required before the full backfill?
- What maximum wall-clock duration and storage growth are acceptable for the bounded benchmark?

## Decisions

### 2026-10-05 - Keep the first backfill path shadow-table based

- **Decision:** Use import-scoped durable raw and shadow tables with one-time shadow indexing,
  validation, and a bounded merge into the current unpartitioned `measurements` table. Do not
  implement partition attach in this phase.
- **Reason:** The current schema is not partitioned, while the historical import needs a durable
  inspectable boundary and rollback scope before touching live measurements.
- **Alternatives rejected:** Immediate table partitioning was deferred because it changes primary
  key, foreign key, query, and migration contracts. Direct live-table ingestion is the behavior
  being replaced for backfills because it caused the observed capacity failure.
- **User feedback:** User explicitly requested the opt-in bulk-backfill path with isolated load,
  deduplication, one-time index building, validation, and merge/attach semantics.
- **Impact on implementation:** Adds a backfill mode/state table, shadow-table lifecycle, merge
  lease and station serialization, import-scoped rollback, and a develop-only benchmark gate.

### 2026-10-05 - Make source ordering and target concurrency explicit

- **Decision:** Deduplicate by `(chunk_index, row_ordinal)` and use one station advisory lock
  for both standard and backfill target writes. Permit rollback through `merged` only before
  post-processing starts.
- **Reason:** Chunks may arrive out of order, retries must not duplicate staged rows, and a
  backfill cannot safely assume that standard imports will remain idle during its lifecycle.
- **Tradeoff:** The lock serializes writes to a station and validation collision counts can
  become stale before merge, but the live unique constraint remains the final correctness gate.

### 2026-10-05 - Implement the first bounded backfill slice

- **Implemented:** Added the additive migration, opt-in API mode/status fields, import-scoped raw
  and shadow tables, deterministic materialization and one-time unique shadow index, validation,
  cursor-based merge, station locking for both modes, rollback endpoint, cleanup, and deployment
  defaults.
- **Deviation:** Automatic Postgres-volume free-space measurement was not added because the API
  and worker do not have a reliable cross-pod view of the database volume. The independent byte
  cap, disabled-by-default flag, and develop benchmark gate are the admission controls for this
  phase.
- **Verification:** Full backend suite passes 294 tests; focused new backfill tests cover mode
  gating and server-generated identifier safety; mypy passes the changed service/model/route set.

## User feedback / decisions

- 2026-10-05: User approved proceeding with an opt-in bulk-backfill path for the historical file.
- 2026-10-05: Design review identified and resolved the cross-chunk ordering and shared-lock
  requirements. The spec now limits rollback-after-merge to the pre-post-processing boundary.
- 2026-10-05: User approved implementation. The first slice is complete and remains disabled by
  default; partition attach and production rollout remain separate approval gates.
