# Upstream

Upstream is an open-source platform for collecting, managing, and publishing environmental sensor data. It provides a full stack for field researchers to capture time-series measurements across a hierarchy of **Campaigns → Stations → Sensors → Measurements**, attach rich metadata, and publish datasets to open data portals.

Upstream is deployed on [TACC Tapis Pods](https://tapis-project.org/) and integrates with [CKAN](https://ckan.org/) for open data publishing.

## Repository Structure

This is the root meta-repository. Each component lives in its own repository, included here as a git submodule.

| Component | Repository | Description |
|---|---|---|
| API | [upstream-docker-pods](https://github.com/wmobley/upstream-docker-pods) | FastAPI backend — campaigns, stations, sensors, measurements, CKAN publish |
| UI | [upstream-ui-pods](https://github.com/wmobley/upstream-ui-pods) | React + Vite frontend — data visualization, map views, time series charts |
| SDK | [upstream-sdk](https://github.com/In-For-Disaster-Analytics/upstream-sdk) | Python SDK for programmatic data access |
| API Client | [upstream-python-api-client](https://github.com/In-For-Disaster-Analytics/upstream-python-api-client) | Auto-generated Python client from OpenAPI spec |

## Getting Started

Clone the full system with all submodules:

```bash
git clone --recurse-submodules https://github.com/wmobley/upstream.git
cd upstream
```

Or, if you've already cloned without submodules:

```bash
git submodule update --init --recursive
```

### Running locally

See each component's README for local setup. A convenience script is provided for starting the full dev environment:

```bash
./dev-upstream.sh
```

## Data Model

```
Campaign
└── Station (one or more per campaign)
    └── Sensor (one or more per station)
        └── Measurement (time-series data points)
```

- **Campaign** — a coordinated data collection effort with metadata, spatial coverage, and publication state
- **Station** — a fixed or mobile data collection site with geospatial location
- **Sensor** — an individual measurement instrument with a defined variable and unit
- **Measurement** — a timestamped, geolocated data point with optional confidence values

## Architecture

- **Backend**: FastAPI + SQLAlchemy + PostGIS (PostgreSQL), deployed as a Tapis Pod
- **Frontend**: React 18 + TypeScript + Tailwind CSS + D3.js + Leaflet, deployed as a Tapis Pod
- **Auth**: Tapis OAuth2 (portals.tapis.io)
- **Publishing**: CKAN integration for open data portal publication

## Citation

If you use Upstream in your research, please cite it using the information in [CITATION.cff](CITATION.cff).

## License

See individual component repositories for license information.
