# Remove CKAN Organization Gating from Read-Only Data Access

**Status:** Implemented

## Objective

Stop using CKAN organization membership as the authorization gate for read-only campaign, station, sensor, measurement, and export endpoints. Authenticated users who can access a project API should be able to read that project's data. Retain CKAN/allocation authorization for mutations and metadata publication operations.

## User need

An authenticated Vital project user can open campaign metadata but receives `404 Access to Campaign unavailable. Improper Allocation` when opening a station because the API compares the campaign's allocation string with the user's CKAN organization identifiers. The user needs consistent read access based on project/API access rather than CKAN publication membership.

## Current code/system summary

- `Campaign.allocation` is documented as a TACC/HPC allocation identifier, but `app/api/dependencies/ckan.py` resolves the user's CKAN organizations and compares them to that field.
- `GET /api/v1/campaigns/{campaign_id}` does not run the CKAN allocation check.
- Read-only station, sensor, and measurement routes still call `check_allocation_permission`; this creates the campaign-visible/station-hidden behavior.
- Measurement reads already distinguish authenticated users from unauthenticated users: authenticated requests can access records, while unauthenticated requests are limited to published station/sensor data.
- Mutation and publication routes use the same helper to restrict edit, delete, publish, and unpublish operations.
- Commit `c08b0bc` intentionally removed CKAN organization filtering from campaign discovery because CKAN membership gates metadata publishing, not data visibility. The read-route cleanup was incomplete.

## Proposed design

1. Remove `get_user_allocations_optional` and `check_allocation_permission` from read-only station, sensor, and export routes.
2. Remove CKAN allocation lookup from the authenticated branch of measurement read access. Preserve the existing rule that unauthenticated requests can only read published station/sensor data.
3. Keep `check_allocation_permission` on campaign/station/sensor/measurement mutations and publication operations, including create, update, delete, publish, unpublish, and permission-reporting endpoints.
4. Enforce entity integrity checks on every read path: station identifiers must belong to the requested campaign, sensor identifiers must belong to the requested station, and missing or mismatched entities must continue returning 404.
5. Keep CKAN organization lookup in publication code where it resolves/validates the CKAN owner organization. This change does not alter CKAN dataset ownership or publication behavior.
6. Update tests to prove authenticated read access no longer depends on CKAN organizations while mutation authorization remains protected.

## Files likely affected

- `upstream-docker-pods/app/api/v1/routes/campaigns/campaign_stations.py`
- `upstream-docker-pods/app/api/v1/routes/campaigns/campaign_station_sensors.py`
- `upstream-docker-pods/app/api/v1/routes/campaigns/campaign_station_sensor_measurements.py`
- Existing route tests under `upstream-docker-pods/tests/`, especially station, sensor, and measurement route tests.
- Potentially `upstream-docker-pods/README.md` or API/auth documentation if current access-control wording describes CKAN as a read gate.

## API/schema changes

No endpoint paths, request schemas, or response schemas change. The authorization behavior changes for authenticated read-only endpoints: CKAN organization membership is no longer required.

## Data flow

Authenticated read:

```text
Tapis bearer token → project API authentication → entity/campaign relationship check → data response
```

Unauthenticated read:

```text
no user → entity lookup → published station + published sensor required → data response or 401
```

Mutation/publication:

```text
Tapis bearer token → user role → CKAN organization/allocation authorization → mutation or publication
```

## Risks and tradeoffs

- Authenticated users with project/API access will be able to read unpublished records that were previously protected by the CKAN gate. This is intentional under the approved policy, but the project boundary must remain enforced by Tapis/API access.
- Removing the read gate may expose data to any user who can obtain a valid token and reach the project API; this is the same trust boundary used by the project API itself and must be documented.
- Some child-detail routes currently fetch by child ID without validating the URL's parent campaign/station ID. The change will add those relationship checks before removing the CKAN gate from affected read routes.
- Existing clients may have treated the 404 as an allocation failure. They should instead receive normal data responses when project access is valid.
- CKAN outages will no longer affect read-only campaign/station/sensor access, reducing availability coupling.
- Mutation and publication paths must retain their checks so users cannot edit or publish datasets solely because they can read project data.

## Alternatives considered

- **Keep the CKAN read gate and add CKAN memberships:** rejected as a workaround because it preserves the semantic mismatch and operational coupling.
- **Replace the read gate with direct per-campaign TAS allocation checks:** deferred because campaign allocations are not uniformly TAS charge codes and the project/API boundary already supplies the intended read scope.
- **Apply the current CKAN check earlier at campaign detail:** rejected because it would make discovery inconsistent with the established policy that CKAN membership controls publication, not data visibility.
- **Remove all allocation checks:** rejected; mutation and publication authorization still require ownership/allocation enforcement.

## Test plan

- Add/update read-route tests for station list/detail, sensor list/detail, sensor exports, measurement reads, confidence intervals, and GeoJSON reads with empty/unrelated CKAN allocations; authenticated requests must succeed when entities are valid.
- Add negative tests proving a station from another campaign and a sensor from another station cannot be retrieved by mixing parent IDs.
- Verify unauthenticated measurement behavior still requires published station/sensor state.
- Verify campaign/station/sensor/measurement mutation and publish/unpublish tests still reject unrelated allocations.
- Run focused route/dependency tests, then the broader backend test suite if focused checks pass.

## Documentation plan

- Update API/auth documentation if it claims CKAN organization membership controls data visibility.
- Document that project/API access controls read access, while CKAN organization membership controls publication and metadata mutations.
- No DSO Architecture page update is expected unless the service's documented authorization contract changes there.

## Rollout/rollback plan

- Roll out as a backend image change after focused and regression tests pass.
- Verify Vital campaign 4/station 3 with an authenticated user who lacks the matching CKAN organization.
- Verify an unrelated user cannot mutate or publish the campaign.
- Roll back by restoring the prior backend image if project-boundary access or mutation authorization is incorrect.
- No database migration or external CKAN mutation is required.

## Open questions

- Whether any project API currently has a broader Tapis permission than the intended data audience; deployment-level Tapis permissions should be checked during rollout.
- Whether user-facing API docs should explicitly describe authenticated access to unpublished data.

## Decisions

### 2026-09-18 - Separate read access from CKAN publication authorization

- **Decision:** Authenticated read access follows project/API access; CKAN allocation checks remain for mutations and publication.
- **Reason:** The user confirmed this policy, and the repository history already states that CKAN membership gates metadata publishing rather than data visibility.
- **Alternatives rejected:** Retaining CKAN as a read gate or adding CKAN memberships as a workaround would preserve technical debt and caused the reported failure.
- **User feedback:** User confirmed the recommended project/API read-access policy.
- **Impact on implementation:** Remove CKAN allocation dependencies from read-only routes, preserve mutation/publication checks, add regression coverage, and update authorization documentation if needed.

### 2026-09-18 - Add parent-relationship checks while removing the read gate

- **Decision:** Validate station-to-campaign and sensor-to-station relationships on read routes as part of this change.
- **Reason:** Removing the legacy CKAN gate broadens the authenticated read path; child IDs must not be usable with unrelated parent IDs.
- **Alternatives rejected:** Leaving the existing parent lookup gaps unchanged would preserve an unrelated authorization/data-integrity risk.
- **User feedback:** This hardening is within the user's approved request to fix the read authorization behavior.
- **Impact on implementation:** Add focused relationship checks and negative tests alongside the CKAN gate removal.

## User feedback / decisions

- 2026-09-18: User confirmed that authenticated users with Vital/API project access should read campaign/station/sensor/measurement data, with CKAN checks reserved for edits and publication.

## Implementation result

- Removed CKAN allocation dependencies from authenticated station, sensor, measurement, and export reads.
- Preserved CKAN allocation checks on campaign/station/sensor/measurement mutations, publication, unpublication, and permission reporting.
- Added station-to-campaign and sensor-to-station relationship checks on the affected read routes.
- Updated README authorization guidance and regression tests.
- Focused verification passed: 55 tests across campaign, station, sensor, measurement, and allocation-dependency suites.
