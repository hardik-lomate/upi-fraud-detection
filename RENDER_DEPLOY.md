# Render Deployment Guide

This repo is now ready to deploy on Render using the blueprint file [render.yaml](render.yaml).

## What this deploys

- `upi-fraud-backend` as a Docker web service from [Dockerfile](Dockerfile)
- `upi-fraud-frontend` as a static site built from [frontend](frontend)

## 1. Push this repo to GitHub

```powershell
git add .
git commit -m "Prepare Render deployment"
git push origin main
```

## 2. Create services from the blueprint

1. Open Render Dashboard.
2. Click New + -> Blueprint.
3. Connect your GitHub repo and select branch `main`.
4. Render reads [render.yaml](render.yaml) and creates both services.

## 3. Fill prompted environment variables

Render will prompt for variables marked `sync: false`.

For backend (`upi-fraud-backend`):

- `CORS_ORIGINS` -> your frontend URL after first deploy, for example `https://upi-fraud-frontend.onrender.com`
- `ANTHROPIC_API_KEY` -> optional
- `REDIS_URL` -> optional

For frontend (`upi-fraud-frontend`):

- `REACT_APP_API_URL` -> your backend URL, for example `https://upi-fraud-backend.onrender.com`

## 4. Redeploy once after URLs are known

After first deploy, copy final public URLs from Render and update:

- frontend `REACT_APP_API_URL`
- backend `CORS_ORIGINS`

Then trigger redeploy for both services.

## Notes

- Backend health endpoint is `/health`.
- Backend now reads Render dynamic port via `${PORT}` in [Dockerfile](Dockerfile).
- Free instances may sleep when idle, causing slow first request.
- Local SQLite files are not durable across redeploys. For persistent data, use Render Postgres/Key-Value.
