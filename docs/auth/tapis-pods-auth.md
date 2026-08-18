# Tapis Pods Authentication

Consolidates what was previously four overlapping root-level files (`TAPIS_AUTH.md`,
`TAPIS_AUTH_QUICKSTART.md`, `TAPIS_AUTH_TESTING.md`, `FRONTEND_AUTH_CHANGES.md`) into one
reference. Covers `upstream-docker-pods` (backend) and `upstream-ui` (frontend).

## Overview

Upstream supports two authentication methods that can coexist:

1. **Tapis Pods headers** — when deployed as a Tapis Pod, the pod proxy injects
   `X-Tapis-Username`, `X-Tapis-Tenant`, `X-Tapis-Site` on every request. Upstream trusts these
   headers without a session or pod-header passthrough of its own.
2. **JWT** (password or Tapis OAuth2 RS256) — retained for local development, standalone
   deployments, and backward compatibility. Tapis headers take precedence when both are present.

## Quickstart (local dev)

**Backend** (`upstream-docker-pods/`):

```env
ENV=dev
ENABLE_DEV_TAPIS_HEADERS=true
# Optional — defaults shown
DEV_TAPIS_USERNAME=testuser
DEV_TAPIS_TENANT=tacc
DEV_TAPIS_SITE=tacc
```

```bash
cd upstream-docker-pods
uvicorn app.main:app --reload
```

**Frontend** (`upstream-ui/`):

```bash
cd upstream-ui
npm run dev
```

Click the **"🔧 Tapis Dev Tools"** widget (bottom-right) → **"Quick Test"** → refresh the page.
You're now authenticated as `testuser@tacc`. The widget and backend middleware both auto-disable
in production builds / when `ENV != dev` — safe to leave enabled in dev branches.

To test a different user without restarting anything, enter custom values in the widget and click
"Set Tapis Headers", or change `DEV_TAPIS_USERNAME`/`DEV_TAPIS_TENANT` in `.env` and restart the
backend.

## Architecture

### Backend (FastAPI)

Tapis Pods sends these headers with each authenticated request:

```
X-Tapis-Username: <tapisusername>
X-Tapis-Tenant: <tapistenantid>
X-Tapis-Site: <tapissiteid>
Internal: <tapisusername>.<tapistenantid>.<tapissiteid>
```

Implementation, in `upstream-docker-pods/`:

- **`app/api/v1/schemas/tapis.py`** — `TapisUser` model; validates and structures incoming headers.
- **`app/api/dependencies/auth.py`**:
  - `get_tapis_user_from_headers()` — extracts Tapis user info from request headers.
  - `get_current_user_unified()` — unified auth: checks Tapis headers first, falls back to JWT.
  - `get_current_user_unified_optional()` — optional variant (public + authenticated content).
  - Tapis headers take precedence over JWT when both are present, to prevent auth bypass.
- All route files use `get_current_user_unified()` / `get_current_user_unified_optional()`.

Flow: request arrives → check Tapis headers → if present, build `User` from them; if absent, fall
back to Bearer JWT → if neither succeeds, `401`.

### Frontend (React + TypeScript)

Implementation, in `upstream-ui/`:

- **`src/utils/tapisAuth.ts`** — `getTapisHeaders()`, `storeTapisHeaders()`, `clearTapisHeaders()`,
  `isTapisAuthenticated()`, `getTapisUser()`, `extractTapisHeadersFromUrl()`, `initializeTapisAuth()`.
- **`src/contexts/AuthContext.tsx`** — supports both auth methods; adds `isTapisAuth` (boolean) and
  `username` (string | null); `checkAuth()` checks Tapis first, then JWT; `logout()` clears both.
- **`src/hooks/api/useConfiguration.ts`** — includes Tapis headers (if Tapis-authenticated) or a
  Bearer token (if JWT-authenticated) on every API request.

On app init, `AuthProvider` calls `initializeTapisAuth()`: checks the URL for
`tapis_username`/`tapis_tenant`/`tapis_site` params, stores them in `sessionStorage` and cleans the
URL if found, otherwise checks `sessionStorage` for an existing session. Tapis state is kept in
`sessionStorage` (not `localStorage`) so it's cleared when the tab closes.

**Routing is intentionally public.** All routes in `src/app/_Router/_Router.tsx` are unwrapped from
`ProtectedRoute` — the backend is the only enforcement point. This was a deliberate change (not a
regression): frontend-enforced auth was redundant under the Tapis Pods model (auth happens at the
pod proxy / backend, and users could always bypass `ProtectedRoute` with dev tools anyway). Real
security is always the backend validating every request; frontend routing is UX only.
`src/app/_Layout/_components/Header/_components/Right.tsx` shows the username with no logout button
under Tapis auth (logout is pod-level, not in-app) versus a logout button under JWT auth.

## Testing

### Method 1 — Dev widget (recommended, no restart)

1. `npm run dev` in `upstream-ui/`.
2. Open **"🔧 Tapis Dev Tools"** (bottom-right).
3. **Quick Test** for the default user, or enter custom username/tenant/site → **Set Tapis Headers**.
4. Refresh. Verify: widget shows "✓ Tapis Authenticated", no logout button, username visible.

### Method 2 — Backend `.env` (requires restart)

```env
ENABLE_DEV_TAPIS_HEADERS=true
DEV_TAPIS_USERNAME=anotheruser
DEV_TAPIS_TENANT=utexas
```

### Method 3 — Browser console (manual)

```javascript
sessionStorage.setItem('X-Tapis-Username', 'testuser');
sessionStorage.setItem('X-Tapis-Tenant', 'tacc');
sessionStorage.setItem('X-Tapis-Site', 'tacc');
sessionStorage.setItem('Internal', 'testuser.tacc.tacc');
location.reload();
```

### Method 4 — URL parameters

```
http://localhost:5173/?tapis_username=testuser&tapis_tenant=tacc&tapis_site=tacc
```

### Testing scenarios

- **Mixed auth fallback**: set `ENABLE_DEV_TAPIS_HEADERS=false`, use the JWT login form, verify JWT
  auth still works standalone.
- **Unauthenticated**: clear all headers/tokens (`sessionStorage.clear(); localStorage.clear();`),
  verify public endpoints still return data and the UI doesn't redirect to `/login`.
- **Backend directly with curl**:
  ```bash
  curl -X GET "http://localhost:8000/api/v1/campaigns" \
    -H "X-Tapis-Username: testuser" -H "X-Tapis-Tenant: tacc" -H "X-Tapis-Site: tacc"
  # Or, with ENABLE_DEV_TAPIS_HEADERS=true, headers aren't required at all:
  curl -X GET "http://localhost:8000/api/v1/campaigns"
  ```
- **CI**: set `ENABLE_DEV_TAPIS_HEADERS=true` and `DEV_TAPIS_USERNAME=test_ci_user` as job env vars
  before running `pytest`.

### Verifying state

- Frontend: React DevTools → `AuthProvider` → `isAuthenticated`/`isTapisAuth`/`username`.
- Backend: logs show which auth method resolved the request; add a temporary route that echoes
  `current_user` and the raw Tapis headers if you need to confirm header pass-through.

## API Reference

Backend (`upstream-docker-pods`):

```python
from app.api.dependencies.auth import (
    get_current_user_unified,           # Required auth (Tapis or JWT)
    get_current_user_unified_optional,  # Optional auth
    get_tapis_user_from_headers,        # Extract Tapis headers
)

@router.get("/endpoint")
async def endpoint(current_user: User = Depends(get_current_user_unified)):
    # current_user.username contains the username from Tapis or JWT
    ...
```

Frontend (`upstream-ui`):

```typescript
import {
  getTapisHeaders,
  isTapisAuthenticated,
  getTapisUser,
  initializeTapisAuth,
  clearTapisHeaders,
} from '@/utils/tapisAuth';

const isAuth = isTapisAuthenticated();
const user = getTapisUser(); // { username, tenant, site, internal? }
```

Self-role lookup — `GET /api/v1/user-roles/me`: returns `{username, role}` for whoever's token
(internal HS256 JWT or raw Tapis bearer token) is presented, no admin gate (unlike the admin-only
`GET /api/v1/user-roles` list). Added so the unified UI's project dropdown can resolve each user's
real per-project DB role (`NONE`/`READ`/`USER`/`APPROVEDADMIN`/`ADMIN`). See
`upstream-docker-pods/docs/design/2026-07-09-unified-ui-tapis-auth-multi-instance.md` for the full
design and decision history.

## Security considerations

1. **Header validation** — backend requires all Tapis headers to be present before trusting them.
2. **Priority** — Tapis headers always take precedence over JWT, to prevent auth bypass via a
   stale/forged JWT when Tapis headers are also present.
3. **Session isolation** — Tapis credentials live in `sessionStorage`, not `localStorage`.
4. **Trust boundary** — the Tapis Pods proxy is the trust boundary; headers are trusted once the
   request reaches the pod, since users can't forge cryptographically-signed Tapis headers.
5. **Dev-mode bypass (2026-07-17)** — `get_current_user` in
   `upstream-docker-pods/app/api/dependencies/auth.py` returns a fake ADMIN user with no token
   check when `ENV=dev`. This now respects `TAPIS_ENFORCE_AUTH_IN_DEV` (the same flag
   `authenticate_user` already honored) — set it `true` on any dev-labeled deployment that's
   actually reachable from a shared/production UI, since the multi-project dropdown auto-queries
   every discoverable project pod at login.
6. **Token fan-out across projects (2026-07-17, accepted risk)** — the unified UI's project
   dropdown sends the same Tapis access token, as a Bearer header, to every discovered project's
   API pod (to resolve `GET /api/v1/user-roles/me`). CORS is currently wildcard
   (`allow_origins=["*"]`) across this API, which widens the token's trust boundary — any reachable
   project pod effectively receives the user's full Tapis token. Accepted as a known risk for now
   (see `upstream-docker-pods/docs/design/2026-07-09-unified-ui-tapis-auth-multi-instance.md`);
   tightening CORS is a separate, larger change affecting every route/client.

## Troubleshooting

**Still seeing the login page in a Tapis Pod** — Tapis headers weren't detected. Check
`sessionStorage` has them, use the dev widget to set test headers, verify headers appear in the
Network tab on initial load.

**`401 Unauthorized` from the API** — backend isn't receiving headers. Check backend middleware is
enabled (`ENABLE_DEV_TAPIS_HEADERS` in dev), verify CORS allows the Tapis headers, check the actual
request headers in DevTools → Network.

**Headers not being applied (dev)** — confirm `.env` has `ENABLE_DEV_TAPIS_HEADERS=true` and
`ENV=dev`, restart the backend after editing `.env`, refresh the frontend after setting headers.

**Mixed auth issues when switching JWT ↔ Tapis** — clear everything
(`localStorage.clear(); sessionStorage.clear(); location.reload();`) and set only the method you
want to test.

## Backward compatibility

No migration needed for existing deployments — the unified auth system detects and uses whichever
method applies automatically. JWT-only deployments keep working exactly as before (login page,
Bearer token, logout button); Tapis Pod deployments get username display and no login page, with
no code changes required on either side.

## Disabling dev tools

Backend: remove or set `ENABLE_DEV_TAPIS_HEADERS=false` in `.env`.
Frontend: the dev widget auto-hides in production builds; in dev, comment out
`<DevTapisAuthHelper />` in `App.tsx` if you want it gone, or just ignore it.

## Future enhancements

1. Tapis token validation (beyond header presence).
2. Role-based access control keyed on Tapis tenant/site.
3. Tapis project/allocation integration.
4. Tapis service tokens for backend-to-backend operations.
5. Audit logging with Tapis user identity.
