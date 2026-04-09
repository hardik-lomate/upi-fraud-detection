# Railway Deployment Guide — UPI Fraud Detection

## What you get on Railway's free tier
Railway gives **$5 of usage credit per month** (no credit card needed to start).
A FastAPI backend on the smallest instance costs roughly $0.10–0.30/month,
so your $5 credit goes a long way.

---

## File changes — apply these before pushing to GitHub

Replace/add these files in your project root:

| File | Action |
|------|--------|
| `Dockerfile` | **Replace** with the fixed version (handles missing `api_keys.json`) |
| `railway.toml` | **Add** (tells Railway how to build the backend) |
| `frontend/Dockerfile` | **Replace** (adds `REACT_APP_API_URL` build arg + SPA nginx routing) |
| `frontend/nginx.conf` | **Add** (fixes React Router 404s on page refresh) |
| `frontend/railway.toml` | **Add** (tells Railway how to build the frontend) |

---

## Step 1 — Push your project to GitHub

1. Create a new GitHub repo (can be private).
2. Copy all files from the zip into the repo root.
3. Apply the file changes listed above.
4. `git add . && git commit -m "railway deploy" && git push`

---

## Step 2 — Create the Railway project

1. Go to [railway.app](https://railway.app) → **Sign in with GitHub**.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your repo. Railway will detect the `Dockerfile` and start building.

This first service will be your **backend**.

---

## Step 3 — Set backend environment variables

In Railway, click on your backend service → **Variables** tab → **Add Variable**:

```
JWT_SECRET_KEY        = some-random-32-char-string-here-abc123
AUTH_REQUIRED         = false          # set to true once you add real API keys
DATABASE_URL          = sqlite:///./fraud_detection.db
CORS_ORIGINS          = https://YOUR-FRONTEND-URL.railway.app
ANTHROPIC_API_KEY     =               # optional — for LLM fraud narratives
```

> **Tip:** Generate JWT_SECRET_KEY with:  
> `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Step 4 — Add the frontend service

1. In your Railway project, click **+ New** → **GitHub Repo** → same repo.
2. Railway may re-detect the root `Dockerfile`. Change it:
   - Go to service **Settings** → **Build** section.
   - Set **Root Directory** to `frontend`.
   - Set **Dockerfile Path** to `Dockerfile`.
3. Add this **build variable** (not a regular env var):
   ```
   REACT_APP_API_URL = https://YOUR-BACKEND-URL.railway.app
   ```
   You get the backend URL from the backend service → **Settings** → **Domains**.

---

## Step 5 — (Optional) Add Redis

Redis is optional — the app falls back to in-memory caching without it.
To add it:

1. In your Railway project, click **+ New** → **Database** → **Redis**.
2. Once created, click on the Redis service → **Connect** tab.
3. Copy the `REDIS_URL` and add it to your backend service variables:
   ```
   REDIS_URL = redis://default:PASSWORD@HOST:PORT
   ```

---

## Step 6 — Update CORS after frontend deploys

Once both services are running:

1. Copy your frontend Railway URL (e.g. `https://upi-frontend-xxxx.railway.app`).
2. Go to backend service → **Variables**.
3. Update `CORS_ORIGINS` to your frontend URL.
4. Railway will redeploy automatically.

---

## Step 7 — Train models (optional)

The app starts without trained models (all predictions are skipped with a warning).
To train, Railway lets you run one-off commands:

1. In your backend service, click **+ New Deployment** → **Terminal** (or use Railway CLI).
2. Run:
   ```bash
   python setup_and_train.py
   ```

> Note: Railway's free-tier filesystem is **ephemeral** — models are lost on redeploy.
> For persistence, use Railway Volumes (available on Hobby plan).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Build fails: `COPY api_keys.json` | Make sure you replaced `Dockerfile` with the fixed version |
| Frontend shows blank page on refresh | Make sure `nginx.conf` is added and frontend `Dockerfile` uses it |
| 401 Unauthorized on all requests | Set `AUTH_REQUIRED=false` in backend env vars |
| CORS errors in browser | Update `CORS_ORIGINS` to your exact frontend Railway URL |
| `JWT_SECRET_KEY` missing warning | Set the variable in Railway → backend → Variables |
