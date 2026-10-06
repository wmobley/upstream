# Reliable CKAN Synchronization for Large CSV Uploads

## Status

Implemented

## Objective

Make large CSV uploads reliable even when CKAN is slow, rate-limited, or temporarily unavailable. A successful database ingestion must remain successful independently of CKAN publication, while CKAN synchronization must use an authorized credential, avoid flooding CKAN, and never leave a broken PostgreSQL connection as an application error after the HTTP response has been sent.

## User need

- **Primary user:** Mobile Sniffer data contributors uploading large sensor/measurement CSV datasets through the Upstream UI; they need a reliable upload workflow and a clear indication of whether local ingestion and CKAN publication succeeded.
- **Secondary users:** Upstream maintainers and operators who need actionable logs and a retryable publication path without manually interpreting hundreds of CKAN warnings.
- **Job-to-be-done:** Upload a large dataset once and know that its measurements are stored, its derived local views are updated, and its CKAN resources are either published or explicitly queued for retry.
- **Current pain:** The upload request returns success, but deferred CKAN synchronization generates authorization failures, a flood of `429 Too Many Requests`, and a PostgreSQL SSL EOF during cleanup. The user cannot tell whether the data itself was stored or only CKAN publication failed.
- **Definition of success:** Authorized uploads store all expected measurement rows; CKAN synchronization does not block or corrupt ingestion; transient CKAN throttling is retried with bounded backoff; authorization failures stop futile follow-on calls; and successful uploads do not produce `Exception in ASGI application` cleanup errors.

## Current code/system summary

- `upstream-ui/src/hooks/station/useUploadData.ts` splits measurement CSVs into approximately 1 MB chunks and uploads them sequentially with an upload session.
- `upstream-docker-pods/app/api/v1/routes/upload_file/upload_csv.py` commits measurement data before finalization and schedules `run_ckan_sync_upload()` with FastAPI `BackgroundTasks`.
- `run_ckan_sync_upload()` opens a SQLAlchemy session, reads campaign/station/schema/sensor data, then performs CKAN network calls while that session remains open. Its `finally` block calls `db.close()`; in production this attempted a rollback over a dead SSL connection and raised `psycopg.OperationalError` after the HTTP 200 response.
- `upstream-docker-pods/app/services/ckan_service.py` sends CKAN requests with the end-user Tapis token and raises immediately on HTTP errors. It does not classify status codes, honor `Retry-After`, or retry 429 responses.
- `sync_sensor_resources()` attempts two resource operations per sensor and continues after each failure. In production upload event 5852, 92 sensors produced 184 attempts: 57 authorization failures and 127 429 responses.
- The existing upload optimization spec intentionally chose a non-durable `BackgroundTasks` implementation for phase 1. This follow-up addresses the failure modes observed in that implementation without requiring a queue in the first corrective release.

## Proposed design

### 1. Establish the correct CKAN publishing identity

Before deployment, verify whether the mobile sniffer upload path is intended to publish using the uploading user's CKAN identity or an application-managed publisher identity.

This remains an operational follow-up and is not changed by this implementation. The upload path continues to use the existing end-user Tapis token and now reports CKAN authorization failures as `authorization_failed` without continuing the resource loop.

- Add a distinct configuration value for the upload publisher credential rather than reusing the broad administrative membership key.
- Keep the credential in the pod secret/config mechanism; never persist it in upload records or log it.
- If policy requires user-attributed CKAN writes instead, repair the package/organization membership for the affected user and retain end-user token publishing. The implementation must not silently broaden permissions.
- Add a read-only startup/diagnostic check that reports the selected auth mode and CKAN organization, without printing credentials.

### 2. Make CKAN requests bounded and rate-limit aware

Extend `CKANService` request handling to:

- Represent HTTP status and response headers in a typed `CKANError` subtype.
- Retry 429 and selected transient 5xx/network failures only for a small bounded number of attempts.
- Honor a valid `Retry-After` value, otherwise use capped exponential backoff with jitter.
- Never retry 403/401 authorization failures.
- Log one aggregated failure per resource after retries rather than dumping the full response body for every attempt.

Update resource synchronization so that an authorization failure for the dataset or first resource stops the remaining resource loop for that upload. A rate-limit exhaustion should mark the sync retryable, not masquerade as a successful publication.

### 3. Release the database session before CKAN network calls

Refactor `run_ckan_sync_upload()` into two phases:

1. Open a short-lived database session and load a detached, primitive snapshot of the campaign, station, metadata schemas, and sensors required by CKAN publication.
2. Close that session before any CKAN HTTP request. Perform all CKAN work using the snapshot.

The cleanup path must catch and contain database-close/rollback errors, invalidate broken connections when possible, and log a concise cleanup warning without propagating an exception into Starlette after the response has been sent.

The snapshot must not retain lazy ORM relationships or a live SQLAlchemy session. The Tapis/publisher credential remains in memory only for the duration of the task.

### 4. Make synchronization state explicit

For the first corrective release, preserve the existing response contract and add structured task logs with:

- `upload_event_id`, station/campaign identifiers, and sync attempt number;
- `auth_mode` without credential material;
- counts of resources attempted, succeeded, authorization-failed, rate-limited, and retryable-failed;
- final state: `completed`, `authorization_failed`, `retryable_failed`, or `skipped`.

A durable outbox/worker remains deferred to a second phase. This implementation retains `BackgroundTasks`, so a process restart can still lose a CKAN sync.

### 5. Preserve local-ingestion semantics

- Keep measurement commits and local post-processing independent of CKAN success.
- Do not retry the CSV upload automatically based on CKAN failures; measurement retry behavior is already idempotent through the measurement conflict key.
- Add an operator/read-only path to inspect upload event 5852 and verify stored counts before attempting any replay.

## Files likely affected

- `upstream-docker-pods/app/api/v1/routes/upload_file/upload_csv.py`
- `upstream-docker-pods/app/services/ckan_service.py`
- `upstream-docker-pods/app/services/ckan_publish.py`
- `upstream-docker-pods/app/core/config.py`
- `upstream-docker-pods/app/db/session.py` only if connection invalidation needs a narrowly scoped helper
- `upstream-docker-pods/tests/test_ckan_service.py`
- `upstream-docker-pods/tests/test_ckan_publish.py`
- New focused upload/CKAN background-task tests under `upstream-docker-pods/tests/`
- `upstream-docker-pods/README.md` and relevant API/service documentation
- Environment/deployment configuration for the new publisher credential, after approval

## API/schema changes

No required upload request or measurement schema change in phase one.

The existing `ckan_sync` response object may gain a more specific status/message if the current schema permits it; otherwise the richer state is emitted in structured logs first. A durable outbox phase would add an upload-sync status table or columns and a status endpoint, but that is explicitly out of scope for this first corrective release.

## Data flow

1. The UI sends chunked CSV data as it does today.
2. The API parses and commits measurements and local upload audit data.
3. On verified finalization, the API schedules CKAN synchronization and returns the upload response.
4. The background task snapshots all CKAN inputs and closes its database session.
5. The task calls CKAN with the existing end-user Tapis token and records authorization failures without continuing the resource loop.
6. CKAN 429/transient failures receive bounded backoff; 401/403 failures stop further resource attempts.
7. The task emits one structured final state and never propagates a dead-session cleanup error into the completed request.
8. Operators can distinguish stored-ingestion success from CKAN-publication success and decide whether to replay publication.

## Risks and tradeoffs

- A service credential can solve package authorization but increases the impact of credential compromise; it must be narrowly scoped and separate from the administrative membership credential.
- Keeping `BackgroundTasks` avoids a new worker deployment but does not guarantee eventual CKAN publication across API restarts.
- Backoff reduces CKAN pressure but can make a single sync task run longer; the retry budget must be capped.
- Aborting after authorization failure prevents a 92-sensor error storm but may leave later resources unpublished; the final state must make this explicit.
- Detaching ORM data before network calls requires careful snapshot coverage; missing fields would cause delayed background failures.
- The Postgres checkpoint pressure may have an independent ingestion-performance cause. Releasing the CKAN task's connection addresses one confirmed risk but does not replace measuring insert batch duration and WAL volume.

## Alternatives considered

- **Only grant the user more CKAN permissions:** This may remove the 403s but does not address 429 flooding or the database connection held during CKAN calls.
- **Only suppress the `db.close()` exception:** This hides the symptom without reducing the long-lived transaction or fixing CKAN authorization/rate limiting.
- **Keep end-user tokens and add retries:** This is appropriate only if CKAN policy explicitly requires user-attributed publication; it does not solve the observed authorization mismatch by itself.
- **Add a durable queue immediately:** Strongest eventual-delivery semantics, but adds a worker, credential-handling, migration, and operational surface. Defer unless guaranteed publication is a current requirement.
- **Disable CKAN sync for uploads:** Protects ingestion but regresses the publication workflow. Prefer bounded, observable synchronization.

## Test plan

### Backend

- Verify 429 responses honor `Retry-After`, retry only within the configured budget, and end in a retryable state.
- Verify 401/403 responses are not retried and stop subsequent resource attempts for the same sync.
- Verify transient network/5xx failures are bounded and aggregated.
- Verify the upload CKAN task closes its DB session before the first CKAN request.
- Verify a broken connection during cleanup is logged and contained rather than raised through Starlette.
- Verify publisher credential selection never logs or persists the raw credential.
- Verify local measurement commits remain successful when CKAN sync fails.
- Verify resource synchronization remains idempotent for already-created resources.

### Production validation

- Read-only verify upload event 5852's inserted/attempted counts and sensor coverage before replaying any CKAN publication.
- Run a small authorized CKAN resource-sync smoke test against one sensor before a full replay.
- Monitor upload response status, background sync states, CKAN 401/403/429 counts, PostgreSQL connection resets, checkpoint duration, and pod restarts.

## Documentation plan

- Document the distinction between local ingestion and CKAN publication in the API/service README.
- Document the new publisher credential name, scope, and rotation procedure without documenting its value.
- Update the DSO Architecture service page if the deployment environment or API behavior changes.
- Add an operator runbook for diagnosing and replaying a failed CKAN sync after verifying local measurement counts.

## Rollout/rollback plan

1. Resolve and approve the CKAN identity/organization mapping in a dry-run or read-only diagnostic.
2. Deploy backend code with the new pacing/retry configuration optional; the current end-user CKAN token path remains unchanged.
3. Run focused tests and a one-sensor production smoke test.
4. Monitor one large upload before replaying older failed CKAN syncs.
5. Roll back the backend image if upload latency, local ingestion, or authorization behavior regresses; leave additive configuration unused.
6. Do not replay or mutate CKAN resources until the user explicitly approves that external write.

## Open questions

- Should mobile sniffer CKAN publication use a narrowly scoped service identity, or must CKAN attribute every resource write to the uploading user?
- Is eventual CKAN publication across API restarts a hard requirement now, or is best-effort background synchronization acceptable for this release?
- Where should the upload event 5852 count verification run, given that no local Kubernetes context is available?
- Should the existing broad `CKAN_ADMIN_API_KEY` be split into separate membership and publishing credentials as part of this change?

## Decisions

### 2026-09-28 — Implement bounded CKAN sync and detached database snapshots

- **Decision:** Implement bounded request pacing/retry, fail-fast authorization handling, explicit background sync status logging, and detached database snapshots before CKAN network calls. Defer credential-policy changes and a durable queue.
- **Reason:** These changes directly address the observed 429 flood and PostgreSQL SSL EOF without changing CKAN permissions or adding a new worker service.
- **Alternatives rejected:** Reusing the broad CKAN administrative credential, replaying production resources during this code change, or adding a durable queue before the immediate failure mode is contained.
- **User feedback:** The user explicitly requested the resilience, pacing, and PostgreSQL session protections.
- **Impact on implementation:** Updated the CKAN client, upload background task, configuration propagation, focused tests, and API README. No CKAN or production deployment writes were performed.

## User feedback / decisions

- 2026-09-28: User approved implementing resilient CKAN synchronization, slower request pacing, fail-fast authorization handling, and safe PostgreSQL session cleanup. Credential-policy changes, CKAN replay, and deployment remain out of scope.
