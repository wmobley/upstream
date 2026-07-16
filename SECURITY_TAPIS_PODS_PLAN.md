# Security Plan for Tapis Pods Deployment

Date: 2026-04-08

This plan is based on the Burp report in `/Users/wmobley/Downloads/2026-04-02-upstream-dso (1).pdf` and the current deployment code in:

- [upstream-ui/nginx.conf](/Users/wmobley/Documents/GitHub/upstream/upstream-ui/nginx.conf)
- [upstream-ui/Dockerfile](/Users/wmobley/Documents/GitHub/upstream/upstream-ui/Dockerfile)
- [upstream-ui/package.json](/Users/wmobley/Documents/GitHub/upstream/upstream-ui/package.json)
- [upstream-docker-pods/templates/upstream-ui-template.json](/Users/wmobley/Documents/GitHub/upstream/upstream-docker-pods/templates/upstream-ui-template.json)
- [upstream-docker-pods/templates/upstream-api-template.json](/Users/wmobley/Documents/GitHub/upstream/upstream-docker-pods/templates/upstream-api-template.json)

## Findings Summary

The report shows:

1. `Strict-Transport-Security` missing on the UI site responses.
2. Public HTTPS responses are cacheable.
3. `sales@geoman.io` appears in the built JS bundle from the `@geoman-io/leaflet-geoman-free` dependency.
4. TLS certificate finding is informational only and not a defect.

## What Is Actually Risky

### 1. Missing HSTS

This is a real issue if the public hostname does not return:

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

For a Tapis Pods deployment, this must be verified on the public URL, not only inside the container. If the Tapis edge proxy strips or overrides headers, fixing only internal nginx is insufficient.

### 2. Cacheable HTTPS response

This needs triage by path.

- `GET /` matters because it serves the SPA shell and runtime config.
- `GET /robots.txt` and `GET /vite.svg` are public static assets and usually do not contain sensitive data.
- Hashed CSS/JS assets are normally safe to cache aggressively.

For this app, the security goal should be:

- `index.html` and `runtime-config.js`: conservative caching (`no-store` or at least `no-cache, must-revalidate`)
- hashed static assets under `/assets/`: long-lived cache is acceptable
- truly public static files like `vite.svg`: acceptable to cache
- authenticated API responses: `Cache-Control: no-store`

### 3. Email address in JS bundle

This is coming from the `@geoman-io/leaflet-geoman-free` package metadata bundled into the app. It is not evidence of leaked internal data. It is low risk.

You have two acceptable options:

- Accept the risk and document it as third-party package metadata in a public client bundle.
- Remove or replace the dependency if your policy requires zero email disclosure findings.

## Test Plan

Run these checks against the actual public Pods endpoints after each change.

### A. Header verification on UI hostname

Replace `$UI_URL` with the real deployment, for example `https://upstream.pods.portals.tapis.io`.

```bash
UI_URL="https://upstream.pods.portals.tapis.io"

curl -sSI "$UI_URL/"
curl -sSI "$UI_URL/runtime-config.js"
curl -sSI "$UI_URL/assets/index-<hash>.js"
curl -sSI "$UI_URL/vite.svg"
curl -sSI "$UI_URL/robots.txt"
```

Verify:

- `Strict-Transport-Security` present on HTTPS responses
- `Cache-Control` policy matches the path type
- `Content-Type` is correct for `robots.txt`

### B. Redirect and downgrade behavior

If HTTP is exposed at all, it should redirect to HTTPS immediately.

```bash
curl -sI "http://upstream.pods.portals.tapis.io/"
```

Verify:

- `301` or `308` redirect to `https://...`

### C. API cache policy

Replace `$API_URL` with the public API base URL.

```bash
API_URL="https://upstreamapi.pods.portals.tapis.io"

curl -sSI "$API_URL/docs"
curl -sSI "$API_URL/openapi.json"
curl -sSI "$API_URL/api/v1/campaigns"
```

For authenticated or potentially sensitive API responses, require:

```http
Cache-Control: no-store
```

### D. Bundle inspection for email disclosure

Build locally and inspect the generated bundle:

```bash
cd upstream-ui
npm ci
npm run build
rg -n "@" dist
rg -n "sales@geoman.io|geoman.io" dist
```

If the only hit is package metadata from Geoman, classify as accepted low risk unless policy says otherwise.

### E. Burp or DAST retest

After header fixes are deployed, rerun the same Burp scan against the same public hostname and compare results.

## Fix Plan

## Phase 1: Fix HSTS and caching in the UI container

Update [upstream-ui/nginx.conf](/Users/wmobley/Documents/GitHub/upstream/upstream-ui/nginx.conf) so the container sends the right headers itself.

Recommended target policy:

- All HTTPS UI responses:
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `/` and `/index.html`:
  - `Cache-Control: no-store`
- `/runtime-config.js`:
  - `Cache-Control: no-store`
- `/assets/*` hashed assets:
  - `Cache-Control: public, max-age=31536000, immutable`
- `/vite.svg` and other public static files:
  - `Cache-Control: public, max-age=86400`

Note: HSTS only has effect over HTTPS. If the Pod terminates TLS before the container, confirm the edge preserves the header.

## Phase 2: Verify Tapis edge behavior

Because Pods traffic may traverse a Tapis-managed proxy, verify whether:

- the proxy forwards `Strict-Transport-Security`
- the proxy rewrites `Cache-Control`
- HTTP is reachable and redirected properly

If the edge strips or overrides headers, fix must be applied at the public ingress layer, not only in the container.

## Phase 3: Tighten API cache policy

Review FastAPI responses and whichever proxy fronts the API.

Minimum expectation:

- authenticated JSON responses: `Cache-Control: no-store`
- docs and schema endpoints: either `no-store` or short-lived `no-cache`

This is more important than the UI static asset caching finding.

## Phase 4: Decide on Geoman email disclosure

Options in order of practicality:

1. Accept risk and note that the address is public third-party package metadata.
2. Upgrade the package and retest in case the bundle changed.
3. Replace Geoman if policy prohibits any third-party email in shipped JS.
4. Add a post-build sanitization step only if you must suppress the finding and cannot replace the dependency.

Option 4 should be the last choice because it is brittle.

## Acceptance Criteria

The deployment passes when all of the following are true:

1. Public UI hostname returns `Strict-Transport-Security` over HTTPS.
2. HTTP requests redirect to HTTPS.
3. `index.html` and `runtime-config.js` are not cacheable by browsers.
4. Authenticated API responses return `Cache-Control: no-store`.
5. Static hashed assets remain cacheable for performance.
6. The Geoman email finding is either eliminated or explicitly accepted as low risk.
7. Burp no longer reports:
   - `Strict transport security not enforced`
   - `Cacheable HTTPS response` for sensitive paths

## Recommended Execution Order

1. Baseline the current public Pods headers with `curl -I`.
2. Patch UI nginx header policy.
3. Deploy to a non-prod Pods environment.
4. Re-run `curl -I` checks on the public hostname.
5. Fix any edge-layer header interference.
6. Add API cache controls if missing.
7. Re-scan with Burp.
8. Document Geoman as accepted risk or replace it.

## Notes Specific to This Repo

- The current UI nginx config is minimal and does not set HSTS or cache headers: [upstream-ui/nginx.conf](/Users/wmobley/Documents/GitHub/upstream/upstream-ui/nginx.conf)
- The Geoman dependency is declared here: [upstream-ui/package.json](/Users/wmobley/Documents/GitHub/upstream/upstream-ui/package.json)
- Pods deployment templates reference public Tapis Pods URLs here:
  - [upstream-docker-pods/templates/upstream-ui-template.json](/Users/wmobley/Documents/GitHub/upstream/upstream-docker-pods/templates/upstream-ui-template.json)
  - [upstream-docker-pods/templates/upstream-api-template.json](/Users/wmobley/Documents/GitHub/upstream/upstream-docker-pods/templates/upstream-api-template.json)

## Suggested Next Step

Implement Phase 1 in the UI nginx config first, then validate on a deployed Pods URL with `curl -I` before making any decision about the Geoman finding.
