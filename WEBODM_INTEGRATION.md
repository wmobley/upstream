# Upstream Suite × WebODM Integration Guide

**Prepared by:** Will Mobley, TACC / In-For-Disaster-Analytics  
**Contact:** wmobley@tacc.utexas.edu  
**Date:** 2026-07-08 (updated 2026-07-14)  
**Status:** Draft — for WebODM team review

---

## Overview

**Upstream Suite** is an environmental sensor data management and visualization platform built at TACC (Texas Advanced Computing Center) for disaster analytics and environmental monitoring research. It stores time-series measurements from field sensors — organized into Campaigns, Stations, and Sensors — with full geospatial support (PostGIS, WGS84).

**WebODM** produces georeferenced aerial products (orthophotos, point clouds, DSMs, DTMs) from drone imagery. The goal of this integration is to link WebODM's processed outputs with Upstream's sensor timeseries, enabling researchers to co-visualize aerial survey products alongside ground-truth sensor data from the same campaign area and time window.

---

## Integration Goals

| Goal | Direction | Priority |
|---|---|---|
| Map completed WebODM tasks to Upstream Campaigns by bounding box / date | WebODM → Upstream | High |
| Register a WebODM task's footprint as a Station within an Upstream Campaign | WebODM → Upstream | High |
| Display WebODM orthophotos on Upstream's Leaflet map alongside sensor data | Upstream UI pull | Medium |
| Trigger WebODM processing from Upstream when imagery is uploaded | Upstream → WebODM | Low / Future |

---

## Upstream Suite — Technical Reference

### Deployment

The Upstream Suite runs as a set of **Tapis Pods** on TACC's `portals.tapis.io` tenant. Each project is a self-contained stack with its own API and database pod. The unified UI discovers available stacks automatically via the Tapis Pods API.

| Environment | UI | API |
|---|---|---|
| Production — UpStream Base | `https://upstream.pods.portals.tapis.io` | `https://upstreamapi.pods.portals.tapis.io` |
| Production — SETx Flux Tower | — | `https://fluxapi.pods.portals.tapis.io` |
| Production — VITAL | — | `https://vitalapi.pods.portals.tapis.io` |
| Development | `https://upstreamdevelop.pods.portals.tapis.io` | `https://upstreamdevelopapi.pods.portals.tapis.io` |
| Local Docker | `http://localhost:3000` | `http://localhost:8000` |
| OpenAPI docs | — | `{API_BASE_URL}/docs` |
| OpenAPI JSON | — | `{API_BASE_URL}/openapi.json` |

The backend is a **FastAPI 0.115** application, Python 3.11+, backed by **PostgreSQL 17 + PostGIS 3.5**.

---

### Authentication

Upstream supports two auth modes. Tapis RS256 JWT tokens take precedence; the legacy password JWT is retained for backwards compatibility.

#### Option 1 — Tapis OAuth2 Token (TACC production, recommended)

Obtain a Tapis access token via the TACC OAuth2 portal (`portals.tapis.io`) and pass it as a Bearer token. The API validates the RS256 signature directly against the Tapis JWKS endpoint — no session or pod-header passthrough required.

**Get a token programmatically:**
```python
from tapipy.tapis import Tapis
t = Tapis(base_url="https://portals.tapis.io", username="<user>", password="<pass>")
t.get_tokens()
token = t.access_token.access_token
```

**Or via the REST token endpoint:**
```http
POST https://portals.tapis.io/v3/oauth2/tokens
Content-Type: application/json

{ "username": "<user>", "password": "<pass>", "grant_type": "password" }
```

Use on Upstream API requests:
```
Authorization: Bearer <tapis_access_token>
```

The token is valid for several hours. For browser-based flows, the unified UI handles the full Tapis OAuth2 authorization-code flow automatically.

#### Option 2 — Password JWT (local / standalone / legacy)

Still supported for local development and older UI integrations:

```http
POST /api/v1/token
Content-Type: application/x-www-form-urlencoded

username=<user>&password=<pass>
```

Response:
```json
{ "access_token": "...", "token_type": "bearer" }
```

Use on subsequent requests:
```
Authorization: Bearer <access_token>
```

---

### Data Model

```
Campaign
  └── Station (one or more per Campaign)
        └── Sensor (one or more per Station)
              └── Measurement (time-series rows per Sensor)
```

All geometry uses **SRID 4326 (WGS84)**. Geometries are returned as GeoJSON in API responses.

#### Campaign

The top-level grouping — typically one per field study or disaster event.

| Field | Type | Notes |
|---|---|---|
| `id` | int | Primary key |
| `name` | string | Unique |
| `description` | string | |
| `contact_name` / `contact_email` | string | |
| `start_date` / `end_date` | datetime (ISO 8601) | |
| `allocation` | string | TACC HPC allocation identifier |
| `geometry` | GeoJSON Geometry | Bounding polygon or multipolygon of the campaign area |
| `location.bbox_*` | float | `bbox_west`, `bbox_east`, `bbox_south`, `bbox_north` |
| `metadata` | JSON object | Extensible key-value metadata (see Metadata Schema section) |

#### Station

A physical or logical monitoring location within a Campaign.

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `name` | string | |
| `station_type` | enum | `"static"` or `"mobile"` |
| `start_date` | datetime | Required |
| `geometry` | GeoJSON Geometry | Point or polygon representing station location |
| `metadata` | JSON object | |

#### Sensor

A single measurement channel at a Station.

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `alias` | string | Human-readable name |
| `variablename` | string | Controlled vocabulary (see Sensor Variables endpoint) |
| `units` | string | e.g., `"m"`, `"°C"`, `"m/s"` |
| `postprocess` | bool | Whether server-side post-processing applies |
| `metadata` | JSON object | |

#### Measurement

Individual time-stamped observations.

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `collectiontime` | datetime (ISO 8601) | |
| `measurementvalue` | float | |
| `geometry` | GeoJSON Point | Per-measurement location (supports mobile sensors) |
| `variablename` | string | Mirrors sensor variable |

---

### REST API Reference

All endpoints are prefixed `/api/v1`.

#### Campaigns

```
GET    /api/v1/campaigns                        List campaigns (paginated)
POST   /api/v1/campaigns                        Create campaign
GET    /api/v1/campaigns/{campaign_id}          Get campaign with stations
PATCH  /api/v1/campaigns/{campaign_id}          Update campaign
DELETE /api/v1/campaigns/{campaign_id}          Delete campaign
```

**Create Campaign — example request:**

```json
POST /api/v1/campaigns
{
  "name": "Hurricane Harvey — Houston 2017",
  "description": "Aerial + ground sensor survey",
  "contact_name": "Will Mobley",
  "contact_email": "wmobley@tacc.utexas.edu",
  "start_date": "2017-08-25T00:00:00Z",
  "end_date": "2017-09-05T00:00:00Z",
  "allocation": "TACC-12345",
  "metadata": {
    "webodm_project_id": 42,
    "webodm_task_id": "abc-123"
  }
}
```

**Create Campaign — example response:**

```json
{ "id": 7 }
```

**List Campaigns — example response item:**

```json
{
  "id": 7,
  "name": "Hurricane Harvey — Houston 2017",
  "location": {
    "bbox_west": -95.8,
    "bbox_east": -95.2,
    "bbox_south": 29.5,
    "bbox_north": 29.9
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [...]
  },
  "summary": {
    "station_count": 3,
    "sensor_count": 12,
    "sensor_types": ["temperature", "water_level"],
    "sensor_variables": ["air_temp", "h2o_level"]
  },
  "start_date": "2017-08-25T00:00:00Z",
  "end_date": "2017-09-05T00:00:00Z",
  "is_published": false
}
```

---

#### Stations

```
GET    /api/v1/campaigns/{campaign_id}/stations
POST   /api/v1/campaigns/{campaign_id}/stations
GET    /api/v1/campaigns/{campaign_id}/stations/{station_id}
PATCH  /api/v1/campaigns/{campaign_id}/stations/{station_id}
DELETE /api/v1/campaigns/{campaign_id}/stations/{station_id}
```

**Create Station — example request:**

```json
POST /api/v1/campaigns/7/stations
{
  "name": "WebODM Flight Footprint",
  "description": "Orthophoto coverage area from WebODM task abc-123",
  "station_type": "static",
  "start_date": "2017-08-27T14:00:00Z",
  "metadata": {
    "webodm_task_id": "abc-123",
    "webodm_project_id": 42,
    "product_type": "orthophoto",
    "gsd_cm": 2.4
  }
}
```

Geometry (GeoJSON polygon) for a station is set separately via PATCH after creation, or can be included via the `geometry` field if the route supports it.

---

#### Sensors

```
GET    /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors
POST   /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors
GET    /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/{sensor_id}
PATCH  /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/{sensor_id}
DELETE /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/{sensor_id}
```

For WebODM integration, sensors represent derived raster-level measurements (e.g., elevation from DSM, NDVI from multispectral imagery).

**Create Sensor — example:**

```json
POST /api/v1/campaigns/7/stations/3/sensors
{
  "alias": "DSM Elevation",
  "variablename": "elevation",
  "units": "m",
  "metadata": {
    "product": "dsm",
    "webodm_task_id": "abc-123"
  }
}
```

---

#### Measurements

```
GET    /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/{sensor_id}/measurements
POST   /api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/{sensor_id}/measurements
GET    .../measurements/confidence-intervals   (aggregated / charting endpoint)
GET    .../stations/{station_id}/measurements/export   (CSV export)
```

**Bulk ingest via CSV:**

```
POST /api/v1/uploadfile_csv/campaign/{campaign_id}/station/{station_id}/sensor
Content-Type: multipart/form-data
file: <CSV file>
```

CSV format: `collectiontime,measurementvalue[,geometry_wkt]`

**Geometry format for individual measurements (WKT):**

```
"POINT(-95.5 29.7)"   (longitude latitude)
```

**Confidence-interval aggregation endpoint:**

```
GET .../measurements/confidence-intervals?start=2017-08-25T00:00:00Z&end=2017-09-05T00:00:00Z&bucket_size=1h
```

Response includes `measurement_time`, `value`, `lower_bound`, `upper_bound`, `std_dev`, `min_value`, `max_value`, `percentile_25`, `percentile_75` per time bucket. Useful for charting time series alongside aerial products.

---

#### Sensor Variables (controlled vocabulary)

```
GET /api/v1/sensor_variables
```

Returns the list of valid `variablename` values. WebODM-derived products may use:

- `elevation` — DSM/DTM heights
- `ndvi` — Normalized Difference Vegetation Index
- `point_density` — point cloud density
- Custom values are accepted as free text if not in the controlled list

---

#### Metadata Schema

Upstream supports configurable metadata schemas per scope (campaign, station, sensor). WebODM can query the schema to understand what metadata fields are expected.

```
GET /api/v1/metadata_schema?scope=campaign
GET /api/v1/metadata_schema?scope=station
GET /api/v1/metadata_schema?scope=sensor
```

---

### CORS

CORS is enforced at the **Tapis Pods networking layer**, not inside the FastAPI application. Each API pod has an explicit `cors_allow_origins` allowlist. The current production allowlist includes:

- `https://upstream.pods.portals.tapis.io` (production UI)
- `https://upstreamdevelop.pods.portals.tapis.io` (development UI)

If WebODM needs to call the Upstream API directly from the browser, its origin must be added to each relevant API pod's CORS config. Contact wmobley@tacc.utexas.edu to request this. Server-side calls (WebODM backend → Upstream API) are not subject to CORS and work without any changes.

Allowed methods: `GET POST PUT PATCH DELETE OPTIONS HEAD`  
Allowed headers: `content-type authorization x-tapis-token x-tapis-tenant x-tapis-username x-tapis-site`

---

### Multi-Instance Project Stacks

The unified Upstream UI supports multiple independent project stacks under a single login. After authenticating via Tapis OAuth2, the UI discovers available stacks by listing all Tapis Pods the user has access to and filtering for API pods whose description begins with `[upstream]`.

| Stack | Display Name | API |
|---|---|---|
| `upstream` | UpStream Base System | `upstreamapi.pods.portals.tapis.io` |
| `flux` | SETx Flux Tower | `fluxapi.pods.portals.tapis.io` |
| `vital` | Virtual Institute for Temporal and Additive Learning (VITAL) | `vitalapi.pods.portals.tapis.io` |
| `upstreamdevelop` | Development | `upstreamdevelopapi.pods.portals.tapis.io` |

Users switch between stacks via a dropdown in the UI header. Each stack is a fully independent database — a Campaign created in one stack is not visible in another. For WebODM integration, target the specific stack that corresponds to the relevant research project.

---

## Proposed Integration Flows

### Flow 1 — WebODM Task Completes → Register in Upstream

When a WebODM task finishes processing, use the Upstream API to record the flight:

1. **Find or create a Campaign** — match on bounding box / date overlap, or create a new one:
   ```
   GET /api/v1/campaigns?bbox_west=...&bbox_east=...   (if bbox filter supported)
   POST /api/v1/campaigns  { name, start_date, end_date, allocation, metadata.webodm_project_id }
   ```

2. **Create a Station** for the flight footprint:
   ```
   POST /api/v1/campaigns/{id}/stations
   { name: "WebODM Task {task_id}", station_type: "static", metadata.webodm_task_id, ... }
   ```

3. **Create Sensors** for each derived product (elevation from DSM, NDVI, etc.)

4. **Ingest sampled raster values** as Measurements (if appropriate — e.g., point-sampled DSM values at sensor locations, or summary statistics per time window).

---

### Flow 2 — Upstream UI Embeds WebODM Orthophotos

Upstream's frontend uses **Leaflet + react-leaflet**. WebODM exposes tile endpoints for processed orthophotos:

```
WebODM tile endpoint: /api/projects/{project_id}/tasks/{task_id}/orthophoto/tiles/{z}/{x}/{y}.png
```

On the Upstream map, add a `TileLayer` when a Station has a `webodm_task_id` in its metadata:

```tsx
// Upstream frontend — react-leaflet
<TileLayer
  url={`${WEBODM_BASE_URL}/api/projects/${projectId}/tasks/${taskId}/orthophoto/tiles/{z}/{x}/{y}.png`}
  attribution="WebODM"
  opacity={0.7}
/>
```

WebODM's tile endpoint requires a valid WebODM session cookie or token. If WebODM and Upstream are deployed on the same domain, cookies are shared. Otherwise, a CORS-accessible token endpoint must be configured in WebODM, or tiles proxied through Upstream.

---

### Flow 3 — Shared Campaign Context

A Campaign in Upstream can carry WebODM project/task identifiers in its `metadata` JSON field. This enables bidirectional lookup:

| From | To | Mechanism |
|---|---|---|
| WebODM task page | Upstream Campaign | Link to `{UPSTREAM_URL}/campaigns/{campaign_id}` stored in WebODM task description |
| Upstream Campaign page | WebODM project | `campaign.metadata.webodm_project_id` links to `{WEBODM_URL}/projects/{id}` |

---

## SDK

A Python SDK is available for server-side integration:

```bash
pip install upstream-sdk
```

```python
from upstream.client import UpstreamClient

client = UpstreamClient(base_url="http://localhost:8000", username="user", password="pass")

# Create a campaign from a WebODM task result
campaign_id = client.campaigns.create(
    name="WebODM Survey 2026-07-08",
    start_date="2026-07-08T00:00:00Z",
    allocation="TACC-WEBODM",
    metadata={"webodm_project_id": 42, "webodm_task_id": "abc-123"}
)
```

SDK source: `upstream-sdk/` in this repository. PyPI: `upstream-sdk`.

---

## Environment & Deployment Notes

| Component | Technology |
|---|---|
| Backend | Python 3.11, FastAPI 0.115 |
| Database | PostgreSQL 17 + PostGIS 3.5 |
| Frontend | React 18, TypeScript, Vite, Leaflet |
| Hosting | TACC Tapis Pods (production); Docker Compose (local) |
| Auth (prod) | Tapis OAuth2 authorization-code flow (RS256 JWT) |
| Auth (local/legacy) | Password JWT via `/api/v1/token` |
| Multi-project | Tapis Pods discovery via `[upstream]` description marker |

**Local development:**

```bash
cd upstream-docker-pods
docker compose up
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

---

## Open Questions for WebODM Team

1. **Auth**: Does WebODM expose its tile and REST API with token-based auth that can be stored in Upstream's Campaign metadata? Or does it require session cookies?
2. **Webhook / event**: Does WebODM have a webhook or callback mechanism for task completion that we can point at the Upstream API?
3. **Footprint geometry**: Is the task bounding box (or full GeoJSON polygon footprint) available from the WebODM API after processing completes?
4. **Tile proxy**: Should Upstream proxy WebODM tiles (to avoid CORS and auth complications), or can WebODM be configured to allow cross-origin tile requests?
5. **Existing metadata fields**: Does WebODM support custom metadata on Projects or Tasks that we can write Upstream Campaign/Station IDs into?

---

## Contact

**Will Mobley** — Upstream Suite lead  
wmobley@tacc.utexas.edu  
GitHub: [In-For-Disaster-Analytics/upstream](https://github.com/In-For-Disaster-Analytics/upstream)
