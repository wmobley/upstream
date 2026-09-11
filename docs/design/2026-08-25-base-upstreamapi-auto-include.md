# Design Spec: Base UpstreamAPI Auto-Include for PT2050-DataX Users

**Status:** Implemented

---

## Objective

Ensure that any user with a PT2050-DataX TAS allocation can see and access the "UpStream Base" instance (`upstreamapi`) in the Instance dropdown, even if they lack Tapis Pods READ permission on the `upstreamapi` pod.

---

## User Need

**Primary user:** Environmental researchers with PT2050-DataX allocation who need to access the base UpStream system.

**Job-to-be-done:** Log in and immediately see/access the base UpStream project without manual Tapis Pods permission grants.

**Current pain:**
- Tapis Pods API (`GET /v3/pods`) only returns pods the user has Tapis READ permission on
- PT2050-DataX allocation is an Upstream-level concept, not a Tapis Pods concept
- Users with PT2050-DataX but no manual Tapis READ grant on `upstreamapi` see empty instance list
- Workaround: admin manually grants Tapis READ, or hardcode `VITE_UPSTREAM_API_URL`

**Definition of success:**
- User with PT2050-DataX logs in → sees "UpStream Base" in instance dropdown
- Selecting it loads upstreamapi with correct role (elevated via PT2050-DataX)
- No manual Tapis Pods permission grant required
- Dynamic project pods (vitalapi, fluxapi, etc.) still respect Tapis Pods permissions

---

## Current Code/System Summary

### Instance Discovery Flow (`upstream-ui/src/contexts/InstanceContext.tsx`)

1. `fetchInstances(tapisToken)` calls Tapis Pods API: `GET /v3/pods` with `X-Tapis-Token`
2. Filters pods: `pod_id` ends with `api` AND `description` starts with `[upstream]`
3. For each candidate, calls `GET {apiUrl}/api/v1/user-roles/me` with Bearer Tapis token
4. Maps response role to Permission (`ADMIN`/`USER`/`READ`/`null`); `null` → drop instance
5. Auto-selects instance: URL `?project=` → persisted → `stackId === 'upstream'` → first in list

### Allocation Check (`upstream-docker-pods/app/api/v1/routes/user_roles.py:37-69`)

- `GET /user-roles/me` calls `elevate_role_for_tas_allocation(username, current_role)`
- Checks PT2050-DataX via `user_has_allocation()` → PyTAS `projects_for_user()`
- 5-minute throttle (`_TAS_CHECK_TTL_SECONDS = 300`)
- Returns elevated role in response

### Configuration

- `upstream-ui/src/hooks/api/useConfiguration.ts:17-24` uses `selectedInstance.apiUrl`
- `VITE_UPSTREAM_API_URL` enables fixed-URL mode (bypasses discovery)

---

## Proposed Design

### Core Change: Always Include Base Instance for PT2050-DataX Holders

In `InstanceProvider` (after `fetchInstances` but before auto-select), add a base instance check:

```typescript
// New constant (configurable)
const BASE_UPSTREAM_API_URL = 'https://upstreamapi.pods.portals.tapis.io';

// After fetching Tapis-discovered instances:
if (hasBaseAllocation) {
  // Prepend or ensure base instance exists in candidates
  candidates.unshift({
    stackId: 'upstream',
    displayName: 'UpStream Base',
    apiUrl: BASE_UPSTREAM_API_URL,
    permission: 'USER', // placeholder; will be resolved by fetchRoleForInstance
  });
}
```

### Allocation Check Implementation

**Option A (preferred): Call upstreamapi `/user-roles/me` directly**

```typescript
async function checkBaseAllocation(tapisToken: string): Promise<boolean> {
  try {
    const resp = await fetch(`${BASE_UPSTREAM_API_URL}/api/v1/user-roles/me`, {
      headers: { Authorization: `Bearer ${tapisToken}`, Accept: 'application/json' },
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    return (data.role || '').toUpperCase() !== 'NONE';
  } catch {
    return false;
  }
}
```

This reuses the existing endpoint that already runs the PT2050-DataX check and throttles.

**Option B: New lightweight endpoint** `/api/v1/allocations/me` returning `{ hasPT2050DataX: boolean }`
- Cleaner separation, but requires backend change

**Option C: Check on login in AuthContext** and cache result
- Avoids extra call during instance discovery
- But allocation could change; needs refresh logic

**Decision:** Start with Option A — zero backend changes, reuses throttled check.

### Integration Point

In `InstanceProvider.load()` (line 363-400), after `fetchInstances` returns:

```typescript
const list = await fetchInstances(tapisToken);

// NEW: Check base allocation and prepend if holder
const hasBase = await checkBaseAllocation(tapisToken);
if (hasBase) {
  const baseInstance = { stackId: 'upstream', displayName: 'UpStream Base', apiUrl: BASE_UPSTREAM_API_URL, permission: 'USER' };
  // Avoid duplicate if Tapis already returned it
  if (!list.some(i => i.stackId === 'upstream')) {
    list.unshift(baseInstance);
  }
}

setInstances(list);
// ... rest of auto-select logic
```

### Configuration

Add env var for base URL (fallback to convention):
```typescript
const BASE_UPSTREAM_API_URL =
  window.__UPSTREAM_CONFIG__?.VITE_BASE_UPSTREAM_API_URL?.trim() ||
  import.meta.env.VITE_BASE_UPSTREAM_API_URL?.trim() ||
  'https://upstreamapi.pods.portals.tapis.io';
```

---

## Files Likely Affected

| File | Change |
|------|--------|
| `upstream-ui/src/contexts/InstanceContext.tsx` | Add `checkBaseAllocation`, integrate in `load()` |
| `upstream-ui/src/hooks/api/useConfiguration.ts` | No change (already uses `selectedInstance.apiUrl`) |
| `upstream-ui/src/utils/tapisAuth.ts` | No change |
| `upstream-docker-pods/app/api/v1/routes/user_roles.py` | No change (reused) |

---

## API/Schema Changes

None required for Option A. The existing `GET /api/v1/user-roles/me` on upstreamapi already returns the elevated role when PT2050-DataX allocation exists.

---

## Data Flow

```
User logs in (Tapis OAuth)
    ↓
AuthContext: stores Tapis token, sets isTapisAuth=true
    ↓
InstanceProvider.load() triggered
    ↓
fetchInstances(tapisToken) → Tapis Pods API → dynamic pods (vitalapi, fluxapi, ...)
    ↓
checkBaseAllocation(tapisToken) → GET upstreamapi/api/v1/user-roles/me
    ↓
If role !== NONE: prepend "UpStream Base" to instances
    ↓
Auto-select logic picks instance (URL param → persisted → 'upstream' → first)
    ↓
useConfiguration() uses selectedInstance.apiUrl for all API calls
    ↓
RoleSyncOnTapisAuth calls /users/me on selected instance
```

---

## Risks and Tradeoffs

| Risk | Mitigation |
|------|------------|
| Extra API call on every login/refresh | Throttled by backend (5 min); negligible overhead |
| upstreamapi URL hardcoded/convention-based | Make configurable via `VITE_BASE_UPSTREAM_API_URL` |
| If upstreamapi down, check fails → base not shown | Fail-open? Fail-closed? Currently fail-closed (safe) |
| User loses PT2050-DataX but still sees base until throttle expires | Acceptable (5 min TTL); same as existing throttle |
| Duplicate `upstream` if Tapis also returns it | Dedup by `stackId` before prepending |
| Bypasses Tapis Pods permission model for base | Intentional — base is special; project pods still gated |

---

## Alternatives Considered

| Alternative | Verdict |
|-------------|---------|
| Service account sync: cron grants Tapis READ on upstreamapi | More infra; eventual consistency; rejected for v1 |
| Tapis group for PT2050-DataX users | Requires Tapis group support; rejected |
| Hardcode `VITE_UPSTREAM_API_URL` in UI deploy | Works but inflexible; doesn't allow multi-pod UI |
| New `/allocations/me` endpoint | Cleaner but requires backend deploy; defer to v2 |
| Check allocation in AuthContext on login | Adds latency to login; decoupled from instance discovery |

---

## Test Plan

1. **Unit/Integration (frontend):**
   - Mock `fetchInstances` returning empty list
   - Mock `checkBaseAllocation` returning true/false
   - Verify base instance included/excluded correctly
   - Verify dedup when Tapis returns `upstream` too

2. **E2E (manual):**
   - User with PT2050-DataX, no Tapis READ on upstreamapi → sees "UpStream Base"
   - User without PT2050-DataX → does not see "UpStream Base"
   - User with both PT2050-DataX and Tapis READ → sees base once (dedup)
   - Selecting base loads upstreamapi with elevated role (USER/ADMIN)

3. **Backend (existing):**
   - `GET /user-roles/me` throttle and elevation already tested

---

## Documentation Plan

- Update `docs/auth/tapis-pods-auth.md` or similar to document base instance behavior
- Note `VITE_BASE_UPSTREAM_API_URL` env var in deployment docs

---

## Rollout/Rollback Plan

**Rollout:**
1. Deploy frontend change (backward compatible — only adds base instance)
2. No backend changes required
3. Feature flag via env var if needed

**Rollback:**
1. Revert frontend commit
2. No data migration needed

---

## Open Questions

1. **Confirmed:** `https://upstreamapi.pods.portals.tapis.io` is the correct production URL for upstreamapi. Configurable via `VITE_BASE_UPSTREAM_API_URL`.
2. **Confirmed:** Display name "UpStream Base".
3. **Confirmed:** 5-minute backend throttle is sufficient; no client-side caching needed.
4. **Confirmed:** `/user-roles/me` is the right check endpoint; reuses existing throttled PyTAS check.

---

## Decisions

- **2026-08-25:** Use Option A — call existing `GET /user-roles/me` on upstreamapi to check PT2050-DataX allocation. Zero backend changes, reuses 5-min throttle.
- **2026-08-25:** Base URL configurable via `VITE_BASE_UPSTREAM_API_URL`, defaults to `https://upstreamapi.pods.portals.tapis.io`.
- **2026-08-25:** Display name "UpStream Base".
- **2026-08-25:** Dedup by `stackId === 'upstream'` to avoid duplicate if Tapis also returns it.
- **2026-08-25:** Fail-closed — if upstreamapi unreachable or check fails, base instance not added (safe default).

## Implementation Notes

- **2026-08-25:** Implemented in `upstream-ui/src/contexts/InstanceContext.tsx`:
  - Added `getBaseUpstreamApiUrl()` function (lines 58-63)
  - Added `checkBaseAllocation(tapisToken)` function (lines 66-83)
  - Modified `load()` callback to call `checkBaseAllocation` after `fetchInstances` and prepend base instance if user has allocation (lines 403-417)
  - Added `VITE_BASE_UPSTREAM_API_URL` to `Window.__UPSTREAM_CONFIG__` type in `src/global.d.ts`
  - Documented new env var in `upstream-ui/.env`
- **2026-08-25:** Build passes (`npm run build` successful)

---

## User Feedback / Decisions

*To be filled during review*
