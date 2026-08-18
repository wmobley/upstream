# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-07-16

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** upstream
- **Description:** Upstream is an open-source platform for collecting, managing, and publishing environmental sensor data. It provides a full stack for field researchers to capture time-series measurements across a hier
- **[2026-08-13] Station dashboard map slot:** `upstream-ui/src/app/StationDashboard/StationDashboard.tsx` always renders a fixed `h-[400px]` section below the header for `StatsSection`. The station coverage map should render for static and mobile stations alike; the old `StationType.Mobile` guard in `StatsSection` caused static/non-mobile stations to show an empty 400px gap and was removed.
- **[2026-08-13] Line Confidence overview brush:** The Line Confidence chart has a reusable `OverviewChart`, but `LineConfidenceChart.tsx` must explicitly render it below `MainChart`. The selected brush domain should also be passed to `useList` as `startDate`/`endDate`; otherwise the all-points `total` cannot reflect the zoomed range.
- **[2026-08-13] Station detail allocation 404:** `upstream-docker-pods/app/api/dependencies/pytas.py` receives normalized CKAN org identifiers, so `Campaign.allocation` must be normalized before exact comparison; otherwise station/detail routes can 404 with "Improper Allocation" while campaign detail still loads.
- **[2026-08-13] Upstream SDK base_url convention:** `upstream-sdk` methods build endpoint paths with `/api/v1` internally. `ConfigManager.base_url` should represent the service root or deployment prefix root, e.g. `https://upstreamapi.pods.portals.tapis.io/dev`, not the full API prefix; normalization now strips a trailing `/api/v1` to prevent `/api/v1/api/v1/token`.
- **[2026-08-13] CKAN station publish conflict flow:** `upstream-docker-pods` now treats CKAN `package_create` 409 as a dataset-name conflict, suggests a new `ckan_dataset_name`, and only patches a matching existing dataset for explicit station publish when `patch_existing_ckan_dataset=true`; `upstream-sdk` exposes both fields.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->
- [2026-08-13] Do not compare raw `Campaign.allocation` directly to CKAN org identifiers returned by `_fetch_user_organizations`; those identifiers are lowercased/trimmed. Use the same `_normalize()` exact comparison on both sides.
- [2026-08-13] Do not pass SDK `base_url` examples that end in `/api/v1`; the SDK appends that prefix itself. If users do pass it, `ConfigManager` should normalize it away while preserving prefixes such as `/dev`.
- [2026-08-13] Do not treat CKAN `package_create` 409 as a generic backend failure. First classify whether it is a matching station-owned dataset that may be patched, or a true name collision that should return a suggested `ckan_dataset_name`.

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- **[2026-08-10]** Cleaned up root-level `.md`/`.py` clutter. Before deciding a doc's fate, verified
  live whether the problem it describes still exists (don't trust doc claims — check the code/prod):
  `CKAN_2X_AUTH_REGRESSION_ISSUE.md` was confirmed fixed via a live CKAN API call with a real Tapis
  JWT (deleted); `SECURITY_TAPIS_PODS_PLAN.md` was confirmed *partially* unresolved via `curl -sSI`
  against production (HSTS/X-Frame-Options/X-Content-Type-Options are set in `nginx.conf` but
  stripped by the Tapis Pods edge proxy) — filed as
  https://github.com/wmobley/upstream-ui-pods/issues/20 and added to project 5, then deleted.
  `TAPIS_AUTH.md`/`TAPIS_AUTH_QUICKSTART.md`/`TAPIS_AUTH_TESTING.md`/`FRONTEND_AUTH_CHANGES.md`
  (one heavily overlapping topic cluster spanning `upstream-docker-pods` + `upstream-ui`) merged
  into `docs/auth/tapis-pods-auth.md`, with short pointer links added to both submodules' READMEs.
  `WEBODM_INTEGRATION.md` moved to `docs/integrations/webodm.md` (self-contained, cross-cutting,
  doesn't belong in one submodule's README). `recreate_fluxapi_from_upstreamapi.py` and
  `rotate_upstream_postgres_passwords.py` moved into `tapis-postgres-backup/ops/` — they already
  imported that project's `config`/`pods`/`backup` modules via a `sys.path` hack pointing at a
  `tapis-postgres-backup` subdirectory; now they're siblings and the hack collapsed to
  `parent.parent`. Crossed a git-repo boundary (meta-repo → nested `tapis-postgres-backup` repo),
  so each repo shows the change on its own side (deletion vs. new file) — not a single atomic move.
