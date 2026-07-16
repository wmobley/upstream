# Tapis Pod Authentication Implementation

This document describes the implementation of Tapis Pods authentication for the Upstream application.

## Overview

The Upstream application now supports authentication through Tapis Pods service. When a user authenticates through Tapis, the Pods service sends authentication headers with each request to the pod, which Upstream uses to identify and authorize users.

## Architecture

### Backend (FastAPI)

#### Authentication Headers

Tapis Pods service sends the following headers with each authenticated request:

```
X-Tapis-Username: <tapisusername>
X-Tapis-Tenant: <tapistenantid>
X-Tapis-Site: <tapissiteid>
Internal: <tapisusername>.<tapistenantid>.<tapissiteid>
```

#### Implementation Files

1. **`app/api/v1/schemas/tapis.py`**
   - Defines the `TapisUser` model for storing Tapis user information
   - Validates and structures incoming Tapis headers

2. **`app/api/dependencies/auth.py`**
   - `get_tapis_user_from_headers()`: Extracts Tapis user info from request headers
   - `get_current_user_unified()`: Unified authentication supporting both Tapis headers and JWT tokens
   - `get_current_user_unified_optional()`: Optional authentication variant
   - Tapis headers take precedence over JWT tokens when both are present

3. **Updated Route Files**
   - All API routes have been updated to use `get_current_user_unified()` or `get_current_user_unified_optional()`
   - This allows seamless support for both authentication methods

#### Authentication Flow (Backend)

1. Request arrives at endpoint with `current_user: User = Depends(get_current_user_unified)`
2. `get_current_user_unified()` first checks for Tapis headers
3. If Tapis headers (`X-Tapis-Username`, `X-Tapis-Tenant`, `X-Tapis-Site`) are present:
   - Extract user information from headers
   - Return `User` object with username from Tapis
4. If no Tapis headers, fall back to JWT token authentication:
   - Extract Bearer token from Authorization header
   - Validate and decode JWT
   - Return `User` object from JWT payload
5. If neither authentication method succeeds, return 401 Unauthorized

### Frontend (React + TypeScript)

#### Implementation Files

1. **`src/utils/tapisAuth.ts`**
   - `getTapisHeaders()`: Retrieves stored Tapis headers from sessionStorage
   - `storeTapisHeaders()`: Stores Tapis headers in sessionStorage
   - `clearTapisHeaders()`: Clears stored Tapis headers
   - `isTapisAuthenticated()`: Checks if user is authenticated via Tapis
   - `getTapisUser()`: Returns Tapis user information
   - `extractTapisHeadersFromUrl()`: Extracts Tapis headers from URL query parameters
   - `initializeTapisAuth()`: Initializes Tapis auth on app startup

2. **`src/contexts/AuthContext.tsx`**
   - Updated to support both Tapis and JWT authentication
   - New fields: `isTapisAuth` (boolean), `username` (string | null)
   - `checkAuth()` first checks for Tapis authentication, then falls back to JWT
   - `logout()` clears both Tapis headers and JWT tokens

3. **`src/hooks/api/useConfiguration.ts`**
   - Updated to include Tapis headers in API requests
   - If Tapis authenticated, sends headers with all API calls
   - If JWT authenticated, sends Bearer token as before

#### Authentication Flow (Frontend)

1. **App Initialization**:
   - `AuthProvider` calls `initializeTapisAuth()` on mount
   - Checks URL for Tapis parameters (`tapis_username`, `tapis_tenant`, `tapis_site`)
   - If found, stores in sessionStorage and cleans URL
   - If not in URL, checks sessionStorage for existing Tapis session

2. **API Requests**:
   - `useConfiguration()` hook checks for Tapis headers
   - If Tapis authenticated, includes headers in API configuration
   - All API calls automatically include appropriate authentication

3. **Logout**:
   - Clears both sessionStorage (Tapis) and localStorage (JWT)
   - Resets authentication state

## Usage

### Deploying in Tapis Pods

When deploying Upstream in a Tapis Pod:

1. Configure the pod to pass authentication headers
2. The pod proxy will automatically inject headers for authenticated requests
3. No additional configuration needed in Upstream

### URL Parameters (Optional)

If Tapis headers are passed as URL parameters on initial load:

```
https://your-pod.tapis.io/?tapis_username=user123&tapis_tenant=tenant456&tapis_site=site789
```

The frontend will automatically:
- Extract and store these parameters
- Clean up the URL (remove parameters)
- Use them for subsequent API requests

### Session Storage

Tapis authentication state is stored in `sessionStorage`:
- `X-Tapis-Username`
- `X-Tapis-Tenant`
- `X-Tapis-Site`
- `Internal`

This ensures authentication persists during the browser session but is cleared when the tab/window is closed.

### Development Mode

For local development, you can simulate Tapis authentication by:

1. Setting sessionStorage values manually:
```javascript
sessionStorage.setItem('X-Tapis-Username', 'testuser');
sessionStorage.setItem('X-Tapis-Tenant', 'testtenant');
sessionStorage.setItem('X-Tapis-Site', 'testsite');
```

2. Or by visiting the app with URL parameters:
```
http://localhost:5173/?tapis_username=testuser&tapis_tenant=testtenant&tapis_site=testsite
```

## Backward Compatibility

The implementation maintains full backward compatibility:

- Existing JWT authentication continues to work
- Applications not running in Tapis Pods use JWT authentication as before
- No breaking changes to existing API contracts
- Both authentication methods can coexist

## Security Considerations

1. **Header Validation**: Backend validates all required Tapis headers are present
2. **Priority**: Tapis headers take precedence over JWT to prevent auth bypass
3. **Session Isolation**: Tapis credentials stored in sessionStorage (not localStorage)
4. **CORS**: Ensure CORS settings allow headers from Tapis Pods proxy
5. **Pod Security**: Trust boundary is at the Tapis Pods service - headers are trusted if request reaches the pod

## Testing

### Backend Testing

Test with curl by including Tapis headers:

```bash
curl -X GET "http://localhost:8000/api/v1/campaigns" \
  -H "X-Tapis-Username: testuser" \
  -H "X-Tapis-Tenant: testtenant" \
  -H "X-Tapis-Site: testsite"
```

### Frontend Testing

1. Set sessionStorage in browser console
2. Visit app with URL parameters
3. Verify authentication state in React DevTools

## Migration Guide

### For Existing Deployments

No migration needed. The unified authentication system automatically detects and uses the appropriate method.

### For New Tapis Pod Deployments

1. Deploy Upstream application to Tapis Pod
2. Configure pod to pass authentication headers
3. Set `VITE_UPSTREAM_API_URL` to point to backend API
4. Users authenticate through Tapis, then access the pod

## API Reference

### Backend Dependencies

```python
from app.api.dependencies.auth import (
    get_current_user_unified,           # Required auth (Tapis or JWT)
    get_current_user_unified_optional,  # Optional auth
    get_tapis_user_from_headers,        # Extract Tapis headers
)

@router.get("/endpoint")
async def endpoint(
    current_user: User = Depends(get_current_user_unified)
):
    # current_user.username contains the username from Tapis or JWT
    pass
```

### Frontend Utilities

```typescript
import {
  getTapisHeaders,
  isTapisAuthenticated,
  getTapisUser,
  initializeTapisAuth,
  clearTapisHeaders,
} from '@/utils/tapisAuth';

// Check if Tapis authenticated
const isAuth = isTapisAuthenticated();

// Get Tapis user info
const user = getTapisUser();
// Returns: { username, tenant, site, internal? }

// Initialize on app startup (done automatically in AuthProvider)
const initialized = initializeTapisAuth();
```

## Troubleshooting

### Headers Not Received

1. Check Tapis Pod configuration
2. Verify pod proxy is injecting headers
3. Check CORS settings allow required headers

### Authentication Failing

1. Verify all required headers present (`X-Tapis-Username`, `X-Tapis-Tenant`, `X-Tapis-Site`)
2. Check backend logs for header extraction errors
3. Ensure headers are properly formatted

### Mixed Authentication

- If both Tapis headers and JWT token present, Tapis takes precedence
- Logout clears both authentication methods
- Refresh page to reinitialize auth state

## Future Enhancements

Potential improvements:

1. Add Tapis token validation
2. Implement role-based access control using Tapis tenant/site
3. Add Tapis project/allocation integration
4. Support Tapis service tokens for backend operations
5. Add audit logging with Tapis user identity
