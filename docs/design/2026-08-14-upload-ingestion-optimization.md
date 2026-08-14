# Upload Ingestion Optimization

## Status

Implemented

## Objective

Optimize CSV measurement uploads so chunked UI uploads no longer repeat expensive post-processing on every chunk, upload responses clearly report what was read/inserted/skipped, and CKAN synchronization no longer blocks the hot ingestion path.

## User need

Users are uploading 1-second measurements split across multiple CSV files. Uploads should complete reliably, should not overload Postgres as accumulated measurement history grows, and should not report a plain successful "Done" state when rows were skipped due to duplicate `(sensorid, collectiontime)` conflicts or other ingest warnings.

## Current code/system summary

- `upstream-ui` currently runs on `main` and chunks measurement CSVs by approximately 1 MB in `upstream-ui/src/hooks/station/useUploadData.ts`.
- Each chunk is sent to `POST /api/v1/uploadfile_csv/campaign/{campaign_id}/station/{station_id}/sensor`.
- `upstream-docker-pods/app/api/v1/routes/upload_file/upload_csv.py` treats every chunk as a full upload request.
- Each request creates a new `UploadFileEvent`, parses the sensors CSV, inserts measurements, refreshes sensor statistics, refreshes station geometry, and attempts CKAN dataset/resource synchronization.
- `upstream-docker-pods/app/utils/upload_csv.py` inserts measurements with `ON CONFLICT DO NOTHING` on `(sensorid, collectiontime)`, but the response only exposes inserted count through the legacy `"Total measurements added to database"` field and does not report attempted rows or duplicate skips.
- CKAN errors are caught as warnings, but CKAN HTTP calls still run inside the upload request and can add latency/noise.
- The attached production logs showed repeated upload `500` responses when Postgres reported `FATAL: the database system is in recovery mode`, with failures occurring around `SELECT update_station_geometry(:station_id)`.

## Proposed design

### 1. Add explicit upload-session and finalization control

Add optional multipart form fields to the upload endpoint:

- `upload_session_id: str | None = None`
- `finalize_upload: bool = True`
- `chunk_index: int | None = None`
- `total_chunks: int | None = None`

The default remains `True` so existing clients keep the current behavior when they upload a whole file in one request.

The UI will set:

- A client-generated `upload_session_id` using `crypto.randomUUID()` for each selected measurements file upload.
- `finalize_upload=false` for all non-final chunks.
- `finalize_upload=true` for the final chunk.
- `chunk_index` and `total_chunks` for logging and response auditability.

The backend will treat client finalization fields as hints, not proof of upload completeness. For chunked UI uploads with `upload_session_id`, the backend will persist chunk receipts in `upload_file_events` and only run finalization when it can verify:

- The finalizing request belongs to the same `campaign_id`, `station_id`, and `upload_session_id`.
- `chunk_index == total_chunks - 1`.
- Successful chunk receipts exist for every chunk index from `0` through `total_chunks - 1`.
- The current chunk inserted or intentionally skipped rows without a database exception.

If the same session already has a finalized receipt, the backend will not run post-processing again. It will return `finalized=true` with `post_processing.status="already_finalized"` and `ckan_sync.status="already_finalized"` so a final-chunk retry can be treated as idempotent.

For legacy clients that omit `upload_session_id`, the backend keeps existing single-request behavior and treats the request as finalized by default.

For non-final chunks, the backend will:

- Parse sensors and measurements.
- Insert measurement rows.
- Return audit counts.
- Skip sensor-stat refresh, station-geometry refresh, and CKAN synchronization.

For the final chunk, the backend will:

- Insert measurement rows.
- Refresh affected sensor statistics once for all aliases in the uploaded sensors CSV, not only aliases with non-empty values in the final measurement chunk.
- Refresh station geometry once.
- Schedule CKAN sync after the response instead of calling CKAN inline.

If the backend receives a finalizing chunk but cannot verify that all expected chunk indexes for the same `upload_session_id` succeeded, it will not run post-processing or CKAN sync. The response must make that state explicit with `finalized=false`, a non-empty error/warning message, and `ckan_sync.status="skipped_incomplete_upload"`. The UI must not show the upload as complete in that case.

### 2. Return structured upload audit data

Extend the backend response with an `audit` object while preserving existing legacy response keys for compatibility.

Proposed response shape:

```json
{
  "upload_event_id": 123,
  "upload_session_id": "5c8e2c30-7f33-4d1c-a8b2-14f4bbd7f8b6",
  "finalized": true,
  "chunk_index": 7,
  "total_chunks": 8,
  "audit": {
    "measurement_rows_read": 10000,
    "measurement_values_attempted": 10000,
    "measurement_values_inserted": 9850,
    "measurement_values_skipped_duplicate": 150,
    "sensor_alias_count": 1,
    "row_errors": []
  },
  "post_processing": {
    "status": "completed",
    "statistics_refreshed": true,
    "station_geometry_refreshed": true
  },
  "ckan_sync": {
    "status": "scheduled"
  },
  "Total sensors processed": 1,
  "Total measurements added to database": 9850,
  "errors": []
}
```

`measurement_values_skipped_duplicate` will be derived from `measurement_values_attempted - measurement_values_inserted` because the only ignored insert path is `ON CONFLICT DO NOTHING` on `(sensorid, collectiontime)`.

`measurement_rows_read` counts CSV data rows after the header, including rows where all sensor alias values are blank. `measurement_values_attempted` counts only non-blank values in known alias columns that were sent to the insert path.

### 3. Track ingestion counts in the CSV utility

Change `process_batch()` and `process_measurements_file()` so they return a structured result instead of only `(total_measurements, errors)`.

The result should include:

- Raw measurement CSV data rows read.
- Candidate measurement values attempted across all alias columns.
- Inserted measurement rows, using SQLAlchemy `rowcount`.
- Duplicate-skipped rows.
- Row/schema errors already emitted today.
- Optional per-alias attempted/inserted/skipped counts if simple to collect without extra queries.

### 4. Defer CKAN sync out of the request path

Use FastAPI `BackgroundTasks` for phase 1 rather than adding a new durable queue. The route will schedule a background CKAN sync only on finalization when all of the following are true:

- `finalize_upload=true`
- A Tapis token is present.
- CKAN is configured.
- A campaign, station, owner org, and affected sensor ids are available.

The background task must:

- Open its own `SessionLocal()` session.
- Re-load campaign, station, metadata schemas, and sensors by ids.
- Call `ensure_station_dataset()` and `sync_sensor_resources()`.
- Log CKAN warnings/errors with upload context.
- Never use ORM objects from the request-scoped session.
- Never persist the Tapis token and never log the raw token. Because the current CKAN helpers require the caller's Tapis token, phase 1 may pass the token only as an in-memory `BackgroundTasks` argument for immediate use in the same API process.

This is intentionally non-durable. If the API process dies after returning the upload response, CKAN sync may not run. That is acceptable for phase 1 because current CKAN upload behavior is already best-effort and warning-only for this path.

### 5. Update UI status messaging

Update `upstream-ui/src/hooks/station/useUploadData.ts` to aggregate per-chunk audit data and pass it through progress.

Regenerate the generated TypeScript API client using `upstream-ui/update-upstream-api-client.sh` after the backend OpenAPI spec includes the new form fields. If local OpenAPI generation is unavailable, do not hand-edit generated files as the first choice; instead, add a small upload-specific wrapper around `fetch` in `useUploadData.ts`, record the deviation, and leave client regeneration as a follow-up.

Update `UploadDataModal` so completion copy distinguishes:

- All attempted rows inserted.
- Some rows skipped as duplicates.
- Row warnings/errors returned by the backend.
- CKAN sync scheduled/skipped status.

Avoid "plain Done" when rows were skipped or warnings exist.

## Files likely affected

- `upstream-docker-pods/app/api/v1/routes/upload_file/upload_csv.py`
- `upstream-docker-pods/app/utils/upload_csv.py`
- `upstream-docker-pods/app/db/models/upload_file_event.py`
- A new Alembic migration adding nullable upload-session/chunk/audit fields to `upload_file_events`.
- `upstream-docker-pods/app/api/v1/schemas/` for upload response models, if we choose a typed response model.
- `upstream-docker-pods/tests/` for focused upload ingestion/finalization tests.
- `upstream-ui/src/hooks/station/useUploadData.ts`
- `upstream-ui/src/app/StationDashboard/_components/UploadDataModal.tsx`
- `upstream-docker-pods/openapi.json` if regenerated as part of the workflow.
- `upstream-ui/openapi.json` and `upstream-ui/packages/upstream-api/` if the generated client is refreshed from the new OpenAPI spec.
- Documentation files listed in the Documentation plan.

## API/schema changes

### Request

Backward-compatible optional multipart form fields:

- `upload_session_id?: string`
- `finalize_upload?: boolean` default `true`
- `chunk_index?: integer`
- `total_chunks?: integer`

### Response

Backward-compatible response extension:

- Add `upload_event_id`.
- Add `upload_session_id`.
- Add `finalized`.
- Add `chunk_index` and `total_chunks`.
- Add structured `audit`.
- Add structured `post_processing`.
- Add structured `ckan_sync`.
- Keep existing response keys used by current clients.

`ckan_sync.status` should be one of `scheduled`, `missing_tapis_token`, `ckan_disabled`, `not_finalized`, `skipped_incomplete_upload`, `already_finalized`, or `skipped_error`.

### Database schema

Add nullable columns to `upload_file_events` so existing rows and legacy clients remain valid:

- `upload_session_id TEXT NULL`
- `campaign_id INTEGER NULL`
- `station_id INTEGER NULL`
- `chunk_index INTEGER NULL`
- `total_chunks INTEGER NULL`
- `measurement_rows_read INTEGER NULL`
- `measurement_values_attempted INTEGER NULL`
- `measurement_values_inserted INTEGER NULL`
- `measurement_values_skipped_duplicate INTEGER NULL`
- `finalized BOOLEAN NOT NULL DEFAULT FALSE`
- `finalized_at TIMESTAMPTZ NULL`

Add a non-unique lookup index on `(campaign_id, station_id, upload_session_id, chunk_index)` where `upload_session_id` is not null. Do not add a unique constraint in phase 1: retrying the same chunk should remain idempotent, with duplicate measurement rows skipped by `(sensorid, collectiontime)` and session completeness based on `COUNT(DISTINCT chunk_index)`.

## Data flow

1. UI reads the selected measurements CSV once and splits it into approximately 1 MB chunks.
2. UI generates one `upload_session_id` for the selected measurements file.
3. UI uploads chunks sequentially with `upload_session_id`, `chunk_index`, `total_chunks`, and `finalize_upload`.
4. Backend creates an `UploadFileEvent` receipt for each chunk and stores campaign/station/session/chunk metadata.
5. Backend parses sensors and inserts candidate measurements.
6. Backend updates the current receipt with audit counts and returns those counts for that chunk.
7. Backend skips expensive maintenance for non-final chunks.
8. On a finalizing chunk with `upload_session_id`, backend first checks whether a prior receipt for the same session is already finalized.
9. If the session is already finalized, backend returns an idempotent `already_finalized` response and does not rerun post-processing.
10. Otherwise, backend checks successful receipts for all distinct chunk indexes `0..total_chunks - 1`.
11. Backend performs sensor statistics and station geometry refresh once only after session completeness is verified.
12. Backend marks the final receipt as finalized, records `finalized_at`, and schedules CKAN sync in a background task only after local post-processing succeeds.
13. UI aggregates audit counts across chunks and displays completion status with inserted/skipped/warning details.

## Risks and tradeoffs

- **Non-durable CKAN background task:** CKAN sync can be lost if the process exits after the response. This is acceptable for phase 1 because CKAN sync is already non-fatal during CSV upload. A durable job table/queue is a future improvement.
- **Short-lived token handoff to background task:** Current CKAN helpers require the caller's Tapis token. Phase 1 keeps that token in memory only and never persists or logs it. A durable queue would need a different credential strategy, such as a service credential or encrypted token reference.
- **Final chunk failure after earlier chunks succeed:** Earlier chunks remain inserted because the current importer commits per batch. The UI will show an error and the user can retry. Duplicate skips should make retry idempotent for already-inserted rows.
- **Incomplete session finalization:** If the final chunk arrives but server-side receipts do not prove all chunks succeeded, the backend will skip finalization and CKAN sync. The UI must surface this as not complete.
- **Additive schema migration:** Upload receipt/audit fields require a migration on `upload_file_events`. The fields are nullable except `finalized`, so existing rows remain valid.
- **Client/server version skew:** New UI fields must be optional on the backend. Existing clients must continue to work with defaults.
- **Generated API client maintenance:** The UI generated client should be regenerated from OpenAPI rather than edited manually. If generation tooling is unavailable locally, use a minimal typed wrapper around `fetch` as a temporary fallback and record the deviation.
- **Skipped count attribution:** `attempted - inserted` is treated as duplicate skip because the insert conflict behavior only ignores `(sensorid, collectiontime)` conflicts. If other `DO NOTHING` paths are added later, this assumption must be revisited.
- **Stats freshness during multi-chunk upload:** Between chunks, sensor statistics and station geometry will be stale. This is acceptable because the UI uploads sequentially and only shows complete status after finalization.
- **Operational error reporting:** The route currently logs and returns `upload_event.id` after rollback. The implementation should cache primitive IDs before risky DB operations so exception handling does not touch expired ORM objects.

## Alternatives considered

- **Run all post-processing in every chunk, but optimize SQL:** Rejected for phase 1 because it keeps the pathological repeated-work behavior.
- **Upload the whole CSV in one request:** Rejected as the only fix because large files may still hit API/proxy timeout or memory limits.
- **Add a durable CKAN/job queue immediately:** Deferred because it adds schema, worker, and operational scope. BackgroundTasks provides a smaller phase-1 improvement.
- **Create a separate upload-session database model:** Deferred for phase 1. Extending `upload_file_events` with session/chunk/audit fields gives enough server-side completeness validation without adding a new aggregate table yet.
- **Add a unique chunk receipt constraint:** Rejected for phase 1 because retrying a chunk after a dropped client connection should not fail at the receipt layer. Completeness can be computed from distinct chunk indexes.
- **Remove chunking entirely from the UI:** Rejected because chunking still protects the API/proxy path for larger files.

## Test plan

### Backend unit/route tests

- Test non-final upload chunk inserts measurements and returns audit counts, but does not call `update_sensor_statistics`, `refresh_geometry`, or CKAN sync.
- Test final upload chunk inserts measurements, verifies session completeness, refreshes statistics once, refreshes station geometry once, marks the receipt finalized, and schedules CKAN sync once when configured.
- Test finalizing chunk with missing prior receipts returns `finalized=false`, reports the missing/incomplete state, and does not run statistics, geometry, or CKAN sync.
- Test duplicate finalizing request returns an idempotent `already_finalized` status and does not run post-processing a second time.
- Test default request with no `finalize_upload` behaves as a complete upload for backward compatibility.
- Test duplicate measurement timestamps produce `measurement_values_skipped_duplicate > 0`.
- Test CKAN scheduling uses primitive ids, does not log/persist raw tokens, and opens a fresh DB session in the background task.
- Test operational errors still return useful upload_event context without touching expired ORM attributes after rollback.
- Test OpenAPI includes the optional multipart fields and response audit fields.

### UI checks

- Verify each selected measurements file gets exactly one `upload_session_id`.
- Verify non-final/final chunk request fields are sent correctly.
- Build the UI after updating request fields/client types.
- Verify progress still displays correct chunk counts.
- Verify completion displays inserted and duplicate-skipped counts.
- Verify plain "Upload complete!" is only shown when no warnings/skips exist.

### Read-only production diagnostics

Before and after deployment, use read-only SQL to distinguish actual missing rows from chart/API limits:

```bash
psql "$DATABASE_URL" -v sensor_id=97 -c "
SELECT
  sensorid,
  COUNT(*) AS measurement_count,
  MIN(collectiontime) AS first_measurement,
  MAX(collectiontime) AS last_measurement
FROM measurements
WHERE sensorid = :sensor_id
GROUP BY sensorid;

SELECT
  date_trunc('hour', collectiontime) AS hour,
  COUNT(*) AS measurement_count
FROM measurements
WHERE sensorid = :sensor_id
GROUP BY 1
ORDER BY 1;
"
```

## Documentation plan

- Update `upstream-docker-pods/README.md` with CSV upload behavior, response audit fields, and CKAN background-sync caveat.
- Update `upstream-ui/README.md` only if upload workflow/user-facing behavior is documented there.
- If DSO Architecture docs are available, update the relevant service/frontend page for the API request/response change. The documented local path `/Volumes/Macintosh HD - Data/Github/DSO-Architecture/docs/` was not present in this environment during investigation.

## Rollout/rollback plan

### Rollout

1. Deploy backend first. New request fields are optional, so old UI keeps working.
2. Run the additive `upload_file_events` migration before or with the backend release.
3. Deploy UI after backend is live.
4. Monitor upload `500` rate, Postgres recovery/restart events, upload processing time, duplicate skip counts, incomplete finalization responses, and CKAN background task warnings.
5. Use read-only DB diagnostics to verify expected timestamp coverage for affected sensor ids.

### Rollback

1. Roll back UI first if progress/completion display regresses.
2. Roll back backend if ingestion behavior regresses.
3. The migration is additive, so rollback can leave the new nullable columns/index unused. A downgrade migration can remove them later if needed.
4. CKAN sync can be re-run manually later from station publish flow or a follow-up admin operation if background sync is missed.

## Open questions

- Should sensor statistics and station geometry refresh run synchronously on the final chunk, or should they also move to a background task? The proposed phase 1 keeps them synchronous so the UI sees fresh local data after completion.
- What production database command path should be used for diagnostics: local `psql`, Tapis pod exec, or an existing admin script?
- Should duplicate rows be treated as warnings only, or should an upload with high duplicate rate surface a stronger UI status?
- Should upload-time CKAN sync remain tied to the caller's short-lived Tapis token, or should upload-time CKAN sync be skipped until a service credential/durable queue design exists?

## Decisions

### 2026-08-14 - Implemented with a fetch wrapper instead of regenerating the UI client

- **Decision:** The chunked upload path in `useUploadData.ts` posts multipart form data via a typed `fetch` wrapper (`postUploadChunk`) because `openapi-generator-cli` is not installed locally and the generated client cannot yet model the new form fields.
- **Reason:** The design's fallback path: if local OpenAPI generation is unavailable, use a small upload-specific `fetch` wrapper and record the deviation.
- **Impact on implementation:** The backend OpenAPI spec (`/openapi.json` when the app runs) now includes the optional fields and `UploadFileCsvResponse`. Regenerating `upstream-ui/packages/upstream-api/` and both `openapi.json` files via `update-upstream-api-client.sh` remains a follow-up. The route's response model (`UploadFileCsvResponse` with `response_model_exclude_none=True`) keeps legacy keys (`Total sensors processed`, `Total measurements added to database`, `Data Processing time`, `errors`, `uploaded_file_sensors/measurements stored in memory`) and adds the structured audit fields.

### 2026-08-14 - Background CKAN task logs warnings only and never persists the token

- **Decision:** The background CKAN task opens its own `SessionLocal()`, reloads campaign/station/schemas/sensors by id, calls `ensure_station_dataset()` and `sync_sensor_resources()`, and logs warnings with upload context. The Tapis token is passed only as an in-memory `BackgroundTasks` argument and is never persisted or logged.
- **Impact on implementation:** Implemented as `run_ckan_sync_upload()` in the route module; `schedule_ckan_sync()` returns `(status, message)` where status is one of `scheduled`, `missing_tapis_token`, `ckan_disabled`.

### 2026-08-14 - Optimize finalization instead of removing chunking

- **Decision:** Keep UI chunking but run expensive backend post-processing only after verified upload-session finalization.
- **Reason:** Chunking still protects the upload path from large requests, but repeated statistics/geometry/CKAN work is the likely load multiplier.
- **Alternatives rejected:** Removing chunking entirely; optimizing the repeated SQL while keeping per-chunk finalization.
- **User feedback:** The user confirmed production serves `main` and asked to implement the finalization, audit response, and CKAN deferral changes.
- **Impact on implementation:** Add optional request fields, persist chunk receipt/audit fields, return audit counts, update UI progress aggregation, and add backend tests.

### 2026-08-14 - Defer CKAN with non-durable BackgroundTasks for phase 1

- **Decision:** Schedule CKAN sync with FastAPI `BackgroundTasks` after final chunk processing succeeds.
- **Reason:** This removes CKAN network failures from the hot upload path without adding a durable worker/schema in the first pass.
- **Alternatives rejected:** Inline CKAN sync; durable job queue in phase 1.
- **User feedback:** The user requested CKAN sync be deferred.
- **Impact on implementation:** Background task must use fresh DB sessions and ids rather than request-scoped ORM objects.

### 2026-08-14 - Use upload session receipts without making retries fail

- **Decision:** Add `upload_session_id` and chunk/audit fields to `upload_file_events`, but do not add a unique chunk constraint in phase 1.
- **Reason:** The server needs enough state to verify chunk completeness before once-per-upload finalization, and chunk retries should remain idempotent.
- **Alternatives rejected:** Trusting client `finalize_upload` alone; adding a separate upload-session table immediately; making `(upload_session_id, chunk_index)` unique.
- **User feedback:** Specialist review flagged client-controlled finalization as unsafe without server-side completeness checks.
- **Impact on implementation:** Finalization queries count distinct successful receipt indexes and skip post-processing when a session is incomplete or already finalized.

## User feedback / decisions

- 2026-08-14: User reported 1-second CSV uploads showing success while apparent trailing data was missing and later files failed with `500`.
- 2026-08-14: User confirmed production is serving `main`.
- 2026-08-14: User approved pursuing: one-time post-processing per upload session, audit-friendly upload responses, and deferred CKAN sync.
