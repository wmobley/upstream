# Tapis Auth Testing - Quick Start

## 🚀 5-Minute Setup

### Backend

1. Edit `upstream-docker/.env`:
   ```env
   ENABLE_DEV_TAPIS_HEADERS=true
   ```

2. Start backend:
   ```bash
   cd upstream-docker
   uvicorn app.main:app --reload
   ```

### Frontend

1. Start frontend:
   ```bash
   cd upstream-ui
   npm run dev
   ```

2. Click **"🔧 Tapis Dev Tools"** button (bottom-right)

3. Click **"Quick Test"**

4. **Refresh page**

✅ You're now authenticated as `testuser@tacc`!

## 🎯 Test Different Users

**Method 1: Dev Widget (No Restart)**
1. Open dev widget
2. Enter username/tenant/site
3. Click "Set Tapis Headers"
4. Refresh page

**Method 2: Backend .env (Requires Restart)**
```env
DEV_TAPIS_USERNAME=anotheruser
DEV_TAPIS_TENANT=utexas
```

## 🔍 Verify It's Working

- Dev widget shows: **"✓ Tapis Authenticated"**
- Backend logs show: Tapis headers received
- API calls include Tapis username

## 🧹 Clear Auth

Click **"Clear Headers"** in dev widget, then refresh.

## 📚 Full Documentation

- **Testing Guide**: See `TAPIS_AUTH_TESTING.md`
- **Architecture**: See `TAPIS_AUTH.md`

## ⚠️ Production

Dev tools automatically disable in production. Safe to deploy!
