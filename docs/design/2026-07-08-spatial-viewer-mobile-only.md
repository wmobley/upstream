# Spatial Viewer — Show Only for Mobile Stations

**Status:** Implemented
**Issue:** wmobley/upstream-ui-pods#8
**Repos:** upstream-docker-pods, upstream-ui

---

## Objective

Conditionally render the `GeometryMap` ("Spatial Viewer") in the station detail UI based on whether
the station is mobile or fixed. Fixed stations have a single known location; the spatial track view
adds no value for them.

---

## User Need

Researchers viewing a fixed station's detail page currently see a `GeometryMap` panel that shows a
single point — visually indistinguishable from the station detail page of a mobile station. The panel
occupies space and creates noise. For mobile stations the map shows a moving track and is meaningful.
The UI should reflect this distinction automatically.

---

## Current Code Summary

### Backend — `upstream-docker-pods`

- `StationType` enum exists in `app/api/v1/schemas/station.py` (lines 11–13):
  ```python
  class StationType(str, Enum):
      MOBILE = "mobile"
      STATIC = "static"
  ```
- `station_type` is a column on the `Station` DB model (`app/db/models/station.py`, line 28).
- `station_type` is accepted in `StationCreate` (line 22) and `StationUpdate` (line 71).
- **Gap:** `station_type` is **absent** from `StationItem` (line 25) and therefore absent from
  `GetStationResponse`, `StationItemWithSummary`, and `StationsListResponseItem`. The field is
  write-only; the API never returns it.
- `get_station()` in `app/services/station_service.py` (line 83) builds `GetStationResponse`
  without `station_type`.
- `get_stations_with_summary()` (line 45) builds `StationItemWithSummary` without `station_type`.
- No DB migration is needed — the column already exists.

### Frontend — `upstream-ui`

- `GeometryMap` (`src/app/common/GeometryMap/GeometryMap.tsx`) renders a Leaflet map for any
  GeoJSON geometry.
- `StatsSection` (`src/app/StationDashboard/_components/StatsSection.tsx`, lines 11–14) renders
  `GeometryMap` behind a single `hasValidGeometry` check — no mobile/static awareness.
- The generated `GetStationResponse` TypeScript type (`packages/upstream-api/models/GetStationResponse.ts`)
  has no `stationType` field.
- `StationType` enum exists in the generated client (`packages/upstream-api/models/StationType.ts`)
  but is only referenced by `StationCreate` and `StationUpdate` models.

---

## Proposed Design

### Decision: removal vs. tooltip

The `GeometryMap` panel will be **completely absent from the DOM** for static stations.
A brief placeholder message will occupy the panel slot so the `StatsSection` card is not
empty — it will read "Fixed station — location does not change over time."

Rationale: a disabled/greyed-out map provides no information and adds visual clutter.
A short text explanation is more honest and informative.

### Default for `null` / unknown `station_type`

Treat `null` as **mobile** (show the map). This preserves existing behavior for stations
created before `station_type` was tracked and avoids silently hiding data from users.

---

## Files Affected

### `upstream-docker-pods`

| File | Change |
|------|--------|
| `app/api/v1/schemas/station.py` | Add `station_type: StationType = StationType.STATIC` to `StationItem` |
| `app/services/station_service.py` | Populate `station_type` in `get_station()` and `get_stations_with_summary()` |
| `openapi.json` | Regenerate after schema change (`python create_openapi.py` or equivalent) |

### `upstream-ui`

| File | Change |
|------|--------|
| `packages/upstream-api/` (generated) | Regenerate client from updated OpenAPI spec — adds `stationType` to `GetStationResponse` |
| `src/app/StationDashboard/_components/StatsSection.tsx` | Add `station_type` conditional around `GeometryMap` |

---

## API / Schema Changes

### Backend schema (`station.py`)

**Before:**
```python
class StationItem(BaseModel):
    id: int
    name: str
    ...
    metadata: Dict[str, Any] | None = None
```

**After:**
```python
class StationItem(BaseModel):
    id: int
    name: str
    ...
    station_type: StationType = StationType.STATIC
    metadata: Dict[str, Any] | None = None
```

`StationType.STATIC` is the default so existing rows with a `NULL` DB value still serialise
without error. (Pydantic uses the field default when the source value is `None`.)

> **Note:** reconsider whether defaulting missing DB values to `STATIC` vs. `MOBILE` is the
> right call — see Open Questions.

### Service layer (`station_service.py`)

Add `station_type=row.station_type` to the `GetStationResponse(...)` constructor (line 83)
and `station_type=row[0].station_type` to the `StationItemWithSummary(...)` constructor
(line 45). Both `row.station_type` and `row[0].station_type` are already available from the
ORM because the column is mapped; no join or query change is required.

### OpenAPI / generated client

After regenerating `openapi.json`, run `./update-upstream-api-client.sh openapi.json` in
`upstream-ui` to regenerate the TypeScript client. This adds `stationType?: StationType` to
`GetStationResponse` and related interfaces.

---

## Data Flow

```
Station DB row
  └─ station_type column (existing, "mobile" | "static" | NULL)
       └─ station_service.get_station()
            └─ GetStationResponse.station_type
                 └─ GET /api/v1/campaigns/{id}/stations/{id}
                      └─ upstream-ui GetStationResponse.stationType
                           └─ StatsSection.tsx
                                └─ station.stationType === "mobile" (or null)
                                     ├─ true  → <GeometryMap .../>
                                     └─ false → <p>Fixed station — ...</p>
```

---

## Risks and Tradeoffs

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Existing stations have `NULL` station_type — map disappears for them if we default to STATIC | Medium | Default to MOBILE in the frontend conditional (treat `null` as mobile, show map) |
| API client regeneration overwrites any local edits to generated files | Low | Generated files are never hand-edited; safe to regenerate |
| `StationItemWithSummary` now includes `station_type` — list endpoints return it too | Acceptable | No breaking change; new field is additive |

---

## Alternatives Considered

1. **Collapsed/disabled map with tooltip** — rejected; adds visual weight without information value.
2. **New boolean `is_mobile` field instead of exposing `station_type`** — rejected; `station_type` already exists and the enum is already in the generated client. A boolean would duplicate state.
3. **Frontend-only workaround using geometry shape** (e.g., LineString → mobile, Point → static) — rejected; geometry type is not a reliable proxy for mobility and would break for mobile stations with sparse tracks.

---

## Test Plan

- [ ] Backend unit test: `get_station()` returns `station_type` in response for both `"mobile"` and `"static"` DB values.
- [ ] Backend unit test: `station_type=None` in DB row → `GetStationResponse.station_type` equals `StationType.STATIC` (Pydantic default).
- [ ] Frontend manual test: mobile station detail page shows `GeometryMap`.
- [ ] Frontend manual test: static station detail page shows placeholder text, no map.
- [ ] Frontend manual test: station with no `station_type` set shows `GeometryMap` (null → mobile default).
- [ ] Regression: `CampaignDashboard`, `CampaignCard`, and chart tooltips that also use `GeometryMap` are unaffected.

---

## Documentation Plan

No user-facing documentation changes required. The behavior change is self-evident from the UI.
`CLAUDE.md` files do not need updating.

---

## Rollout / Rollback

- No DB migration — the column already exists.
- The backend change is additive (new field in response). Old frontends receiving the new response
  will silently ignore `station_type`.
- Rollback: revert the `StationItem` field addition and redeploy. The frontend falls back to always
  showing the map (current behavior).

---

## Open Questions

1. **Default for `NULL` station_type:** The schema default of `StationType.STATIC` means untagged
   stations will show a placeholder instead of a map. The frontend conditional default (treat `null`
   as mobile) inverts this. Which direction is safer for your dataset — are most existing stations
   mobile or static?

2. **Should `StationItemWithSummary` / list endpoints also expose `station_type`?** The spec adds
   it because `StationItemWithSummary` inherits from `StationItem`. This is probably fine, but confirm
   it doesn't break any consumers of the station list API.

---

## Decisions

*(Record approvals, tradeoffs, and implementation deviations here as they occur.)*
