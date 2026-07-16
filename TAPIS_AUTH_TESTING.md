# Testing Tapis Authentication Locally

This guide shows you how to test Tapis Pod authentication in your local development environment without actually running in a Tapis Pod.

## Overview

We've created two testing tools:
1. **Backend Middleware** - Automatically injects Tapis headers in dev mode
2. **Frontend Dev Tool** - UI widget to set test Tapis headers

## Quick Start

### Backend Setup

1. **Add to your `.env` file in `upstream-docker/`:**

```env
ENV=dev
ENABLE_DEV_TAPIS_HEADERS=true

# Optional: Customize test user (defaults shown below)
DEV_TAPIS_USERNAME=testuser
DEV_TAPIS_TENANT=tacc
DEV_TAPIS_SITE=tacc
```

2. **Start your backend:**

```bash
cd upstream-docker
# Your normal start command, e.g.:
uvicorn app.main:app --reload
```

The middleware will now automatically inject Tapis headers into all requests!

### Frontend Setup

**Option 1: Using the Dev Tools Widget (Recommended)**

1. Start your frontend in development mode:

```bash
cd upstream-ui
npm run dev
```

2. Look for the **"🔧 Tapis Dev Tools"** button in the bottom-right corner

3. Click it to open the widget and either:
   - Click **"Quick Test"** to use default test user (`testuser@tacc`)
   - Or enter custom values and click **"Set Tapis Headers"**

4. **Refresh the page** to apply the headers

5. You're now authenticated via Tapis! Check the widget to see your current auth state.

**Option 2: Manual Setup via Browser Console**

```javascript
// Set test headers
sessionStorage.setItem('X-Tapis-Username', 'testuser');
sessionStorage.setItem('X-Tapis-Tenant', 'tacc');
sessionStorage.setItem('X-Tapis-Site', 'tacc');
sessionStorage.setItem('Internal', 'testuser.tacc.tacc');

// Refresh the page
location.reload();
```

**Option 3: URL Parameters**

Visit your app with query parameters:

```
http://localhost:5173/?tapis_username=testuser&tapis_tenant=tacc&tapis_site=tacc
```

The app will automatically extract and store these headers.

## Testing Scenarios

### Scenario 1: Test with Default User

**Backend + Frontend Together:**

1. Enable backend middleware in `.env`:
   ```env
   ENABLE_DEV_TAPIS_HEADERS=true
   ```

2. Use frontend dev widget to set `testuser@tacc`

3. All API calls will now be authenticated as `testuser`

### Scenario 2: Test Different Users

**Test authorization with different users:**

```bash
# In your .env, change the test user
DEV_TAPIS_USERNAME=anotheruser
DEV_TAPIS_TENANT=utexas
DEV_TAPIS_SITE=austin
```

Or use the frontend widget to switch between users without restarting.

### Scenario 3: Test Mixed Authentication

**Test fallback from Tapis to JWT:**

1. Disable Tapis headers:
   ```env
   ENABLE_DEV_TAPIS_HEADERS=false
   ```

2. Use JWT authentication (existing login form)

3. Verify JWT auth still works

### Scenario 4: Test Without Authentication

**Test public endpoints:**

1. Clear Tapis headers using the dev widget's "Clear Headers" button

2. Or manually clear sessionStorage:
   ```javascript
   sessionStorage.clear();
   location.reload();
   ```

3. Navigate to public endpoints to verify they still work

## Verification

### Check Backend Is Receiving Headers

Add a test endpoint in your routes:

```python
@router.get("/test/auth")
async def test_auth(
    request: Request,
    current_user: User = Depends(get_current_user_unified)
):
    return {
        "authenticated": True,
        "username": current_user.username,
        "headers": {
            "X-Tapis-Username": request.headers.get("X-Tapis-Username"),
            "X-Tapis-Tenant": request.headers.get("X-Tapis-Tenant"),
            "X-Tapis-Site": request.headers.get("X-Tapis-Site"),
        }
    }
```

Then visit: `http://localhost:8000/api/v1/test/auth`

### Check Frontend Auth State

Open React DevTools and inspect the `AuthProvider` state:

- `isAuthenticated` should be `true`
- `isTapisAuth` should be `true`
- `username` should show your test username

Or check the dev tools widget which displays current auth state.

## Testing API Calls

### Using curl

Test backend directly with curl:

```bash
# Test with Tapis headers
curl -X GET "http://localhost:8000/api/v1/campaigns" \
  -H "X-Tapis-Username: testuser" \
  -H "X-Tapis-Tenant: tacc" \
  -H "X-Tapis-Site: tacc"

# If dev middleware is enabled, you don't need headers:
curl -X GET "http://localhost:8000/api/v1/campaigns"
```

### Using Postman/Insomnia

1. Create a new request
2. Add headers:
   - `X-Tapis-Username: testuser`
   - `X-Tapis-Tenant: tacc`
   - `X-Tapis-Site: tacc`
3. Send request

### Using Frontend

Just use the app normally! With the dev widget or middleware enabled, all requests will include Tapis headers.

## Troubleshooting

### Headers Not Being Applied

**Backend:**
- Check `.env` has `ENABLE_DEV_TAPIS_HEADERS=true`
- Verify `ENV=dev`
- Restart backend after changing `.env`
- Check backend logs for middleware messages

**Frontend:**
- Refresh page after setting headers
- Check sessionStorage in browser DevTools
- Verify headers are in `useConfiguration` hook

### Getting 401 Unauthorized

- Verify headers are set correctly (check browser DevTools > Network tab)
- Check backend logs to see which auth method is being used
- Ensure middleware is enabled if testing backend directly

### Mixed Auth Issues

If switching between JWT and Tapis:

1. Clear everything:
   ```javascript
   localStorage.clear();
   sessionStorage.clear();
   location.reload();
   ```

2. Set only the auth method you want to test

## Disabling Dev Tools

### Backend

Remove or set to false in `.env`:

```env
ENABLE_DEV_TAPIS_HEADERS=false
```

### Frontend

The dev widget automatically hides in production builds. For development, you can:

1. Comment out `<DevTapisAuthHelper />` in `App.tsx`
2. Or just ignore it - it's unobtrusive

## Advanced: Custom Test Users

Create different test user profiles:

**Option 1: Environment Variables**

```env
# User 1 (default)
DEV_TAPIS_USERNAME=admin_user
DEV_TAPIS_TENANT=tacc
DEV_TAPIS_SITE=tacc

# Restart backend and use admin_user
```

**Option 2: Multiple .env Files**

```bash
# .env.user1
ENABLE_DEV_TAPIS_HEADERS=true
DEV_TAPIS_USERNAME=user1
DEV_TAPIS_TENANT=tacc

# .env.user2
ENABLE_DEV_TAPIS_HEADERS=true
DEV_TAPIS_USERNAME=user2
DEV_TAPIS_TENANT=utexas

# Load different env
cp .env.user1 .env
# or
cp .env.user2 .env
```

**Option 3: Frontend Widget**

Just use the widget to switch between users instantly without backend restart.

## Integration with Real Tapis Pod

When deploying to a real Tapis Pod:

1. Remove or set `ENABLE_DEV_TAPIS_HEADERS=false`
2. The dev widget won't appear in production
3. Real Tapis headers will be used automatically

No code changes needed - the unified auth system handles both!

## Example Workflow

**Full Development Testing Flow:**

1. **Start Backend:**
   ```bash
   cd upstream-docker
   # Ensure .env has ENABLE_DEV_TAPIS_HEADERS=true
   uvicorn app.main:app --reload
   ```

2. **Start Frontend:**
   ```bash
   cd upstream-ui
   npm run dev
   ```

3. **Set Test User:**
   - Click "🔧 Tapis Dev Tools" in bottom-right
   - Click "Quick Test"
   - Refresh page

4. **Test Features:**
   - Navigate to campaigns
   - Create/edit/delete resources
   - Verify username appears as "testuser"

5. **Test Different User:**
   - Open dev widget
   - Change username to "poweruser"
   - Click "Set Tapis Headers"
   - Refresh page
   - Verify different permissions/behavior

6. **Test Logout:**
   - Click "Clear Headers" in dev widget
   - Refresh page
   - Should see login screen

## CI/CD Considerations

For automated testing:

```bash
# In your test scripts
export ENABLE_DEV_TAPIS_HEADERS=true
export DEV_TAPIS_USERNAME=test_ci_user

# Run tests
pytest

# Or in GitHub Actions
env:
  ENABLE_DEV_TAPIS_HEADERS: true
  DEV_TAPIS_USERNAME: test_ci_user
```

## Security Notes

⚠️ **Important:**

- The dev middleware ONLY works when `ENV=dev`
- The dev widget ONLY appears in development builds
- Never deploy with `ENABLE_DEV_TAPIS_HEADERS=true` in production
- Real Tapis Pods use cryptographically signed headers - dev mode bypasses this

The dev tools are safe because:
1. They only activate in development mode
2. Production builds exclude them automatically
3. Real Tapis authentication is cryptographically verified at the pod level

## Summary

| Method | Frontend | Backend | Best For |
|--------|----------|---------|----------|
| Dev Widget | ✓ | - | Quick UI testing |
| Backend Middleware | - | ✓ | API testing |
| Both Together | ✓ | ✓ | Full stack testing |
| URL Parameters | ✓ | - | Sharing test links |
| Browser Console | ✓ | - | Manual control |

Choose the method that best fits your testing workflow!
