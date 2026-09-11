# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-07-16

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

- **[2026-09-04] Upstream end-user docs should not list mutable project/development API URLs as a canonical set. Explain how users find the project instances they personally have access to through the UI project selector and selected project's API docs link instead.**

## Key Learnings

- **Project:** upstream
- **[2026-09-11] UI CKAN publishing:** Upload/ingestion creates the deterministic station CKAN dataset before publication. UI station and campaign publish hooks must send `patchExistingCkanDataset: true` so the backend patches the existing dataset and makes it public.
- **[2026-09-11] CKAN measurement resource URL:** The per-sensor CKAN resource is labeled GeoJSON and must target the pods API's `/measurements.geojson` route; `/measurements` is the paginated non-GeoJSON endpoint.
- **[2026-09-11] Project discovery authorization:** `upstream-ui/src/contexts/InstanceContext.tsx` resolves each discovered project's own `/api/v1/user-roles/me`; `NONE`/401/403 hides that project. The separate `checkBaseAllocation()` call is only for conditionally adding the base `upstream` instance, and must not be used as a prerequisite for unrelated project instances such as `vitalapi`.
- **Description:** Upstream is an open-source platform for collecting, managing, and publishing environmental sensor data. It provides a full stack for field researchers to capture time-series measurements across a hier
- **[2026-09-03] DSO Architecture docs path drift:** The repo instructions name `/Volumes/Macintosh HD - Data/Github/DSO-Architecture/docs/Codex-context/...`, but this machine's accessible symlinked docs are under `/Users/wmobley/Documents/Github/DSO-Architecture/docs/claude-context/...`. Use the symlink form and `claude-context` pages when the `Codex-context` path is missing.
- **[2026-08-13] Station dashboard map slot:** `upstream-ui/src/app/StationDashboard/StationDashboard.tsx` always renders a fixed `h-[400px]` section below the header for `StatsSection`. The station coverage map should render for static and mobile stations alike; the old `StationType.Mobile` guard in `StatsSection` caused static/non-mobile stations to show an empty 400px gap and was removed.
- **[2026-08-13] Line Confidence overview brush:** The Line Confidence chart has a reusable `OverviewChart`, but `LineConfidenceChart.tsx` must explicitly render it below `MainChart`. The selected brush domain should also be passed to `useList` as `startDate`/`endDate`; otherwise the all-points `total` cannot reflect the zoomed range.
- **[2026-08-13] Station detail allocation 404:** `upstream-docker-pods/app/api/dependencies/pytas.py` receives normalized CKAN org identifiers, so `Campaign.allocation` must be normalized before exact comparison; otherwise station/detail routes can 404 with "Improper Allocation" while campaign detail still loads.
- **[2026-08-13] Upstream SDK base_url convention:** `upstream-sdk` methods build endpoint paths with `/api/v1` internally. `ConfigManager.base_url` should represent the service root or deployment prefix root, e.g. `https://upstreamapi.pods.portals.tapis.io/dev`, not the full API prefix; normalization now strips a trailing `/api/v1` to prevent `/api/v1/api/v1/token`.
- **[2026-08-13] CKAN station publish conflict flow:** `upstream-docker-pods` now treats CKAN `package_create` 409 as a dataset-name conflict, suggests a new `ckan_dataset_name`, and only patches a matching existing dataset for explicit station publish when `patch_existing_ckan_dataset=true`; `upstream-sdk` exposes both fields.
- **[2026-08-20] Bethel actor fetch/upload dedupe split:** `bethel1Base/fetch_tilt_telemetry.py` with `FETCH_MODE=missing` compares remote CSV filenames against local files in `LOCAL_OUTPUT_DIR` only. The Tapis registration points this at `/work/bethel1Base/data/out` with `stateless=True`; if that path is not durable across actor executions, the actor will re-download every remote `tilt_telemetry_*.csv` each run. `upload_to_upstream.py` separately filters transformed rows by API timestamps on an anchor sensor, and backend upload inserts use `ON CONFLICT DO NOTHING` on `(sensorid, collectiontime)`.
- **[2026-08-20] Bethel actor deployment IDs:** The deployable Bethel actor under the local `tasclient_dsso` credentials may not match stale hardcoded IDs in helper scripts. On 2026-08-20, stale `zyoq4PDywXqbN` was inaccessible, while visible old actor `zXPqA0LbGJqvk` was deleted and replaced by `0xv3vpRMKYBXO` using image `ghcr.io/wmobley/bethel1base:watermark-20260820-193534`.
- **[2026-08-20] Stale actor token check:** A user-provided `wmobley` Tapis access token also received `Not authorized -- you do not have access to this actor` for stale actor id `zyoq4PDywXqbN`; do not assume that ID can be cleaned up from the current local credential set.
- **[2026-08-20] Bethel actor production image architecture:** Tapis actor workers require the Bethel image to be runnable on linux/amd64. A Docker Desktop local push from Apple Silicon produced `exec /usr/bin/tini: exec format error`; use `docker buildx build --platform linux/amd64 --push` for production actor images.
- **[2026-08-20] Bethel actor ownership:** Tapis Actors have a single `owner` field plus permissions. To make `wmobley` the owner, create/recreate the actor using a `wmobley` Tapis access token, then grant `tasclient_dsso` `UPDATE`; the successful actor is `0ZajqbE1Vyxxk`.
- **[2026-08-24] Manuscript code availability wording:** `latex/upstream-alaska.tex` now frames the artifact paragraph as a Code availability statement with explicit GitHub repository URLs for root, API, UI, SDK, generated Python client, and Bethel actor source. The current Bethel image reference is `ghcr.io/wmobley/bethel1base:watermark-20260820-2005-amd64`; the Bethel actor source checkout has no local tag or license file, so do not claim a Bethel source version or license without new verification.
- **[2026-09-04] react-leaflet MapContainer immutability:** `MapContainer` from react-leaflet ignores prop changes to `center`/`zoom` after mount. To update the map view dynamically, use a child component with `useMap()` + `useEffect` to call `map.flyTo()` or `map.setView()`. The initial `center` prop is only used for the first render.
- **[2026-09-04] Sensor Route data volume mismatch:** `StatsSection` (Sensor Route map) was using `limit=500, downsampleThreshold=500` while `RouteMapViz` used `limit=500000, downsampleThreshold=5000`. The low limit meant only 500 measurements were fetched, showing a small subset of the actual data. Aligned both to use the same larger values.
- **[2026-09-05] uPlot commit() defers to a microtask:** `u.setScale()`/`u.setData()` schedule their internal `commit()` via `queueMicrotask`, so hooks like `setScale` do NOT fire synchronously after the call — a ref flag set/reset immediately around a plain `setScale` call will already be reset by the time the hook actually runs. Use `u.batch(fn)` (documented as "skips implicit microtask queue") to force synchronous commit + hook firing when you need to bracket a hook with a guard flag.
- **[2026-09-05] LineConfidenceProvider had no `key`:** React Router reused the same `LineConfidenceViz`/`LineConfidenceProvider` instance across sensor navigations (no `key` on the provider), so `useState` in `LineConfidenceContext.tsx` (selectedTimeRange, min/maxFilterValueInput, additionalSensorInfos) leaked from the previously-viewed sensor into the new one. Keyed the provider by `${campaignId}-${stationId}-${sensorId}` instead of trying to manually enumerate every piece of state to reset.
- **[2026-09-05] uPlot `setScale` fires for non-interactive scale changes too:** The hook fires for uPlot's own internal auto-ranging (establishing the initial scale from data on construction, or after `setData`), not just real user drag/zoom. `u.cursor.event` is only ever set by a genuine DOM mouse event and persists as "most recent", so `if (u.cursor.event == null) return;` correctly filters out non-interactive firings (each fresh instance starts with it unset) without blocking real zoom. Root-caused via headless Playwright: added console.log with `isProgrammaticScaleUpdate.current` + mount/unmount logging in `UPlotChart.tsx`, which proved the component was genuinely unmounting/remounting every refetch cycle (not just re-rendering).
- **[2026-09-05] TanStack Query v5 clears `data` to `undefined` mid-refetch by default:** Any `{someQueryData && (...)}` render gate (e.g. `Chart.tsx`) unmounts its subtree on every refetch triggered by a changed queryKey unless `placeholderData: keepPreviousData` is set. Combined with the uPlot auto-range issue above, this turned a single spurious scale-read into an unbounded unmount/remount/refetch loop (`selectedTimeRange`'s end date walked backward ~1hr per cycle). Added `placeholderData: keepPreviousData` to `useListConfidenceValues.ts` and `useList.ts`.
- **[2026-09-05] uPlot AlignedData x-array must never contain null:** `AlignedData = [xValues: number[], ...yValues: (number|null|undefined)[][]]` -- only the y-series arrays may hold null; the x-array type has no null variant. `uPlotDataTransform.ts` was pushing `null` into the x (time) array as a gap separator, which corrupted uPlot's internal auto-range min/max (null coerces to 0 in numeric comparisons), squeezing real data into a sliver at one edge of a scale that effectively spanned from epoch 0. Fix: push a real monotonic timestamp (e.g. `lastTs + 1`) with null y-values instead.
- **[2026-09-05] uPlot `spanGaps: true` means the OPPOSITE of what it sounds like:** per uPlot's own docs, "when true, null data values will not cause line breaks" -- i.e. `true` bridges over gaps, `false` breaks the line at them. A codebase comment describing the gap-null-insertion logic said "spanGaps breaks lines" while the code set `spanGaps: true` everywhere -- backwards. Always check the doc string, not the option name's intuition.
- **[2026-09-05] uPlot `Series.value` callback signature:** `(self, rawValue, seriesIdx, idx)` -- the 2nd arg is already the resolved value for that series at the cursor, not an index. Re-indexing via `u.data[seriesIdx][rawValue]` (treating rawValue as an index) silently returns undefined for real timestamps/values.
- **[2026-09-05] Playwright for headless repro of this app:** `npx playwright install chromium` works standalone; the `playwright` npm package isn't a project dependency, so `require('playwright')` needs a scratch dir with its own `npm install playwright --no-save` (module resolution is relative to the script's location, not cwd — `npx -p playwright node script.js` alone does NOT make it requirable). To authenticate: `sessionStorage.setItem('Tapis-Access-Token', <jwt>)` plus `X-Tapis-Username`/`X-Tapis-Tenant` (decoded from the JWT's `tapis/username`/`tapis/tenant_id` claims) is enough for `initializeTapisAuth()`/`getTapisUser()` in `src/utils/tapisAuth.ts` to treat the session as logged in — set these on the app's own origin (`page.goto('http://localhost:3000/')` first) before navigating to the target route.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->
- [2026-09-04] Do not hard-code a static list of Upstream project API URLs in end-user docs; those project instances can change and access differs by user. Document discovery via the project selector/API docs link instead.
- [2026-08-13] Do not compare raw `Campaign.allocation` directly to CKAN org identifiers returned by `_fetch_user_organizations`; those identifiers are lowercased/trimmed. Use the same `_normalize()` exact comparison on both sides.
- [2026-08-13] Do not pass SDK `base_url` examples that end in `/api/v1`; the SDK appends that prefix itself. If users do pass it, `ConfigManager` should normalize it away while preserving prefixes such as `/dev`.
- [2026-08-13] Do not treat CKAN `package_create` 409 as a generic backend failure. First classify whether it is a matching station-owned dataset that may be patched, or a true name collision that should return a suggested `ckan_dataset_name`.
- [2026-08-20] Do not use Bash 4-only lowercase expansion (`${VAR,,}`) in `bethel1Base/entrypoint.sh`; local validation may run under macOS Bash 3. Use the portable `lowercase()` helper instead.
- [2026-08-20] Do not trust old hardcoded Tapis actor IDs before actor replacement. First list visible actors with the deployment credentials, confirm the actor name/image/owner, and only delete the actor that account can actually manage.
- [2026-08-20] Do not publish Bethel Tapis actor images from local Docker without `--platform linux/amd64`; the Tapis worker may fail at `/usr/bin/tini` before entrypoint code runs.

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
