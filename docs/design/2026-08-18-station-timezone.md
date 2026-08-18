# Station Timezone + TIMESTAMPTZ Measurement Storage

## Status

Implemented

## Objective

Fix the Upstream platform's timezone-less measurement timestamp pipeline so users who upload CSVs with local-time `collectiontime` values (e.g., Chicago local time) no longer see their data shifted ~5 hours in the UI (the "missing last 5 hours" bug). Naive timestamps will be interpreted in a station-declared IANA timezone and stored as aware `TIMESTAMPTZ` instants; aware timestamps pass through unchanged.

## User need

A user uploads CSV measurements where `collectiontime` is written in Chicago local time. The platform currently stores these as `TIMESTAMP WITHOUT TIME ZONE` and the UI parses the offset-less serialized value as browser-local time, so the user's data appears shifted by the UTC offset (looks like the last ~5 hours are missing). Users need a way to declare what timezone their naive timestamps are in, per station, so all consumers (API, UI, SQL aggregations) see the correct UTC instant.

## Current code/system summary

- `upstream-docker-pods/app/db/models/measurement.py`: `measurements.collectiontime` is `Mapped[datetime]` with no `DateTime(timezone=True)` → column is `TIMESTAMP WITHOUT TIME ZONE` (migration `15da413ffe54_.py`).
- `upstream-docker-pods/app/utils/upload_csv.py` (`process_measurements_file`, lines 331-346): CSV `collectiontime` values are inserted verbatim as naive datetimes.
- `upstream-docker-pods/app/db/repositories/measurement_repository.py`: `create_measurement`/`bulk_create_measurements` store naive datetimes as given.
- `upstream-docker-pods/app/utils/lttb.py` (line 62): LTTB downsampling produces naive `datetime.fromtimestamp(avg_x)` (server-local time), which Pydantic serializes without an offset → the ~5h shift survives in every `downsample_threshold` response (live path: `useList.ts`/`useListFilterDate.ts` in `upstream-ui`).
- `upstream-docker-pods/alembic/versions/80811109be28_create_confidence_values_function.py`: `get_sensor_aggregated_measurements` SQL function takes/returns `TIMESTAMP` and casts bounds as `::TIMESTAMP`; `date_trunc` bucketing operates on naive values.
- `upstream-ui/src/hooks/measurements/useProcessedMeasurements.ts` (line ~82): `new Date(item.collectiontime)` treats offset-less strings as browser-local.
- `bethel1Base/transform_tilt_telemetry.py` (line ~106): writes `row["time_utc"]` (UTC) into `collectiontime` as a naive value.
- `bethel1Base/upload_to_upstream.py` (lines 105-106): `normalize_collectiontime` does `isoparse(value).isoformat()`; once the API returns aware `"...Z"` values, this naive-vs-aware comparison breaks the dedupe logic.
- The platform has no timezone concept anywhere: `stations` has no timezone column, and the UI has no way to declare one.

## Proposed design

### 1. Required per-station IANA timezone

- Add `stations.timezone VARCHAR(64) NOT NULL` (IANA name, e.g. `America/Chicago`, `UTC`).
- **Required on station create** (`StationCreate.timezone`), optional on partial update (`StationUpdate.timezone`). Both validated against `zoneinfo.available_timezones()` at the schema level → 422 on invalid names (prevents `ZoneInfoNotFoundError` → 500 DoS on every upload for a bad station).
- **No coordinate-derived fallback** (rejected — see Alternatives): naive data must never be silently interpreted via geometry, because UTC-logging clients (e.g., bethel1Base) would be mislocalized. `timezonefinder` is not added to the backend.
- Migration backfills existing stations with `'UTC'` (server default), preserving the current interpretation of their naive data (consistent with "existing data left as-is"). bethel1Base stations remain correct as UTC; other stations can be corrected via the edit form.

### 2. Aware measurement storage

- `measurements.collectiontime` → `TIMESTAMPTZ`, migration: `USING collectiontime AT TIME ZONE 'UTC'` so existing naive values keep their instant.
- New `upstream-docker-pods/app/utils/timezone.py`:
  - `localize_collectiontime(value, tz)` — accepts `datetime`/`pd.Timestamp`/`str`; naive → `value.replace(tzinfo=ZoneInfo(tz))`; already-aware → passthrough unchanged.
- Applied at every measurement write path:
  - CSV upload: `process_measurements_file` (station tz fetched by the upload route and passed in).
  - `MeasurementRepository.create_measurement` / `bulk_create_measurements`.
  - PUT/PATCH measurement update endpoints (`app/api/v1/routes/campaigns/campaign_station_sensor_measurements.py`).
- `Measurement.collectiontime` model → `mapped_column(DateTime(timezone=True))`.

### 3. SQL function and downsampling awareness

- `get_sensor_aggregated_measurements`: `p_start_date`/`p_end_date` params, `measurement_time` return column, and `$2::TIMESTAMP`/`$3::TIMESTAMP` casts → `TIMESTAMPTZ`. **Must `DROP FUNCTION` before recreate** — `CREATE OR REPLACE` fails when argument types change.
- `lttb.py` line 62: `datetime.fromtimestamp(avg_x, tz=timezone.utc)`.

### 4. bethel1Base protection

- `transform_tilt_telemetry.py`: append `Z` to `collectiontime` when the value is not already aware (writes aware UTC regardless of any station tz setting).
- `upload_to_upstream.py::normalize_collectiontime`: parse with `isoparse`, attach UTC if naive, then `.astimezone(timezone.utc).isoformat()` so naive-file values and aware API responses compare on the same UTC basis (fixes the dedupe break).

### 5. UI

- `CreateStationForm.tsx`: required timezone select, pre-filled with a **suggestion** computed from the campaign bounding-box centroid via `tz-lookup` (hint only — the user must confirm; not a fallback).
- `StationDashboard.tsx` edit-metadata modal (~lines 181-200, 554): timezone field.
- `UploadDataModal.tsx`: show the station's timezone in the upload help text.
- Regenerate `@upstream/upstream-api` client so `StationCreate`/`StationUpdate` carry `timezone`.

## Files likely affected

- `upstream-docker-pods/alembic/versions/` (new revision)
- `upstream-docker-pods/app/db/models/station.py`, `app/db/models/measurement.py`
- `upstream-docker-pods/app/utils/timezone.py` (new), `app/utils/upload_csv.py`, `app/utils/lttb.py`
- `upstream-docker-pods/app/api/v1/schemas/station.py`
- `upstream-docker-pods/app/db/repositories/station_repository.py`, `measurement_repository.py`
- `upstream-docker-pods/app/api/v1/routes/upload_file/upload_csv.py`
- `upstream-docker-pods/app/api/v1/routes/campaigns/campaign_stations.py`, `campaign_station_sensor_measurements.py`
- `bethel1Base/transform_tilt_telemetry.py`, `bethel1Base/upload_to_upstream.py`
- `upstream-ui/src/app/Station/_components/CreateStation/CreateStationForm.tsx`
- `upstream-ui/src/app/StationDashboard/StationDashboard.tsx`
- `upstream-ui/src/app/StationDashboard/_components/UploadDataModal.tsx`
- `upstream-sdk` regenerated client (`upstream/campaigns.py`, `upstream/stations.py`)

## API/schema changes

- `stations.timezone` column added (NOT NULL, server default `'UTC'` on backfill).
- `measurements.collectiontime` type change `TIMESTAMP` → `TIMESTAMPTZ`.
- `StationCreate.timezone` required (string, validated IANA name); `StationUpdate.timezone` optional.
- `get_sensor_aggregated_measurements` signature/return types `TIMESTAMP` → `TIMESTAMPTZ`.
- API responses now serialize `collectiontime` with a UTC offset (e.g. `"...+00:00"`).

## Data flow

1. Station create/update declares an IANA timezone.
2. Measurement writes localize naive `collectiontime` in that timezone → stored as `TIMESTAMPTZ` (absolute UTC instant).
3. API serializes aware datetimes with offset; UI `new Date(...)` parses correctly regardless of browser locale.
4. SQL aggregation (`date_trunc` bucketing) operates on aware timestamps, so day/hour boundaries are correct UTC instants.
5. bethel1Base writes aware UTC → immune to station tz settings.

## Risks and tradeoffs

- **Naive-UTC uploads to existing `'UTC'`-backfilled stations**: unchanged behavior (data interpreted as UTC). Users who know their CSVs are local-time must set the station timezone via edit form.
- **Migration data conversion is irreversible**: naive→aware via `AT TIME ZONE 'UTC'` cannot be reversed losslessly; rollback documented as data-risk.
- **`DROP FUNCTION` + recreate** of `get_sensor_aggregated_measurements` — the new version must preserve exact bucketing semantics for aware values.
- **IANA name validation** is mandatory at the schema boundary (security review: `ZoneInfo` raises on invalid names → 500).
- **DST-ambiguous local times** (fall-back hour) resolve to the earlier offset; documented limitation.
- **UI suggestion accuracy** (`tz-lookup` from bbox centroid) is approximate; the user confirms before submit.

## Alternatives considered

- **Campaign-level timezone field** — rejected: stations in one campaign can span timezones (mobile stations); per-station is the correct granularity.
- **UI-only fix (display-side timezone label)** — rejected: the API returns no timezone marker, so the UI cannot distinguish UTC vs local-time data; would not fix SQL aggregation or the SDK.
- **Coordinate-derived fallback when `timezone` is unset** (original plan, using `timezonefinder`) — rejected after skeptic review: silently mislocalizes naive UTC data uploaded to flag-less stations by any client other than bethel1Base. Timezone is now **required** on create.
- **Backfill existing stations from geometry** — rejected: would mislocalize bethel1Base's UTC data; `'UTC'` backfill preserves current behavior.

## Test plan

- Update existing tests that use naive `datetime.utcnow()`: `tests/test_campaign_station_sensor_measurement_routes.py`, `tests/test_upload_csv_ingestion.py`, `tests/test_measurement_service.py`, `tests/api/test_campaign_station_sensors.py`.
- New unit tests:
  - `localize_collectiontime`: naive→aware, aware passthrough, DST Jan vs Jul, DST-ambiguous, invalid tz names, str/Timestamp/datetime inputs.
  - Schema validation: missing `timezone` on create → 422; invalid name → 422.
  - Upload paths: Chicago station + Chicago-local CSV → correct UTC instants; aware passthrough; mixed naive/aware in one file.
  - Migration: backfill `'UTC'`; SQL function `TIMESTAMPTZ` semantics; `date_trunc` bucketing.
  - bethel1Base dedupe: naive file values vs aware API responses compare consistently.
- UI (no test framework): manual verification checklist for timezone select + bbox suggestion.

## Documentation plan

- `upstream-docker-pods/README.md` (~lines 79-92)
- `upstream-ui/README.md` (~lines 447-493)
- `upstream-sdk/README.md` (~lines 249-269)
- `upstream-sdk/CLAUDE.md` (~line 145)
- `upstream-sdk/upstream/sensors.py` docstring (~lines 280-292)

Convention to document: *naive timestamps are interpreted in the station's declared timezone; aware timestamps pass through unchanged; timezone is required on station create.*

## Rollout/rollback plan

1. Backend migration + API first (existing stations default `'UTC'` = no behavior change).
2. bethel1Base aware-UTC writes.
3. UI + SDK client regeneration.
Rollback: revert the alembic revision. The naive→aware data conversion is irreversible; the downgrade converts back assuming UTC.

## Open questions

None — all decisions resolved during review.

## Decisions

- Timezone is **required** on station create; no coordinate fallback (user decision after skeptic review, 2026-08-18).
- Existing stations backfill to `'UTC'` (user approved; geometry backfill rejected because it would mislocalize bethel1Base UTC data).
- Naive values are interpreted in the station's declared timezone; aware values pass through.
- bethel1Base writes aware UTC and normalizes dedupe comparisons to UTC.
- `lttb.py` downsampled timestamps become aware UTC (QA/QC gap closed).
- tz names validated against `zoneinfo.available_timezones()` at schema level (security review).
- Design spec required before implementation (user decision).

## User feedback / decisions

- 2026-08-18: user selected "Require timezone on station create" for the fallback-risk question.
- 2026-08-18: user approved the finalized plan ("do it").

## Implementation notes / deviations

- Migration adds the column as `NOT NULL DEFAULT 'UTC'`; PostgreSQL fills existing rows with the default, so no separate backfill `UPDATE` is needed.
- bethel1Base `transform_tilt_telemetry.py` emits fully aware ISO strings (`2026-01-15T14:30:00+00:00`) via `isoparse` instead of literally appending `Z` — same effect (explicit UTC instant), robust to any source format.
- Client regeneration (`@upstream/upstream-api`) exposed stale generated files (`ProjectsApi.ts`, `PyTAS*.ts`) left from an older backend spec that no longer has project/PyTAS endpoints. They referenced models the new spec no longer defines and broke `tsc`. Removed them plus the dead `upstream-ui/src/hooks/projects/` hook (imported nowhere). This is collateral cleanup required by the approved regen, not a feature change.
- Added `src/utils/timezones.ts` (shared `TIMEZONES` list + `suggestedTimezoneFor`); added `tz-lookup` + `@types/tz-lookup` dependencies.
- Backend lint: `black` was applied to `app/db/models/station.py`, `app/db/models/measurement.py`, and `app/api/v1/schemas/station.py` (small files; drift was within sections adjacent to the edits). Pre-existing black/isort/flake8 drift in larger files (`station_service.py`, `station_repository.py`, upload route, `measurement_repository.py`) was confirmed at HEAD and left untouched.
- Test plan: new unit tests cover `localize_collectiontime`, schema validation (missing/invalid timezone → 422 at both model and API level), and the upload path (Chicago-local CSV → correct UTC instants, aware passthrough, UTC default). bethel1Base dedupe verified with an inline script.
- Full station update (PUT) now requires `timezone` (400 if absent) — consistent with the required-on-create decision.
- **Local e2e verification (2026-08-18):** ran the full pipeline against a real local PostGIS 16 container (port 5434): migration applied, API exercised via TestClient with auth overrides. All 24 e2e checks pass: create-campaign/station flows, 422s, Chicago-local uploads → correct UTC instants (Jan CST -6 → 20:30Z, Jun CDT -5 → 19:30Z), aware passthrough (+02:00 → 08:00Z), API serialization with UTC offset, confidence-intervals SQL function on TIMESTAMPTZ, PUT tz change, and PATCH localization (naive 12:00 on 2024-03-10 → 16:00Z, correctly EDT -4).
- **Pre-existing bug found and fixed during e2e:** SQLAlchemy's psycopg3 dialect reports `rowcount = -1` for multi-row `INSERT ... ON CONFLICT DO NOTHING` against a real database, corrupting the upload audit counts (`measurement_values_inserted`/`skipped_duplicate`). `process_batch` now counts actual insertions via `RETURNING` (skipped conflict rows are not returned), giving exact counts; the corresponding tests were updated to mock the returned rows. Mock-based tests had hidden this because they faked `rowcount`.
- **Regression found during local UI testing:** `GET /campaigns/{id}` (`CampaignService.get_campaign_with_summary`) built station items without `timezone`, which is now a required field on `StationsListResponseItem` → 500 ValidationError (surfaced in the browser as a confusing CORS error, since Starlette's unhandled-500 responses carry no CORS headers). Fixed by adding `timezone=station.timezone`; regression test added (`TestCampaignDetailIncludesStationTimezone`).