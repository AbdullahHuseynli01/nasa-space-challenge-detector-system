# Deployment guide

The dashboard (`frontend/`) runs on **Vercel**; the API (`backend/`) runs on **Render** at
`https://nasa-challenge-backend-nil7.onrender.com`. In production the browser calls the
API directly, so the two must agree on one thing: the backend's `CORS_ORIGINS` must list
the dashboard's exact URL.

**Order:** (1) confirm the backend settings, (2) deploy the frontend, (3) put the
frontend's URL into `CORS_ORIGINS`, (4) verify.

## 1. Backend on Render

The service is already deployed; these are the settings to confirm.

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` (not rate-limited) |

Environment variables:

| Variable | Value | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | With this set, the app refuses to start unless `CORS_ORIGINS` is set. |
| `CORS_ORIGINS` | `https://your-project.vercel.app` | Exact origin(s), comma-separated. No `*` (rejected), no path. Add custom domains too. |
| `GROQ_API_KEY` | your key | Without it, AI explanations return "not configured". |
| `RATE_LIMIT_REQUESTS` | `5` (or more) | Requests per window per client. Default 3. |
| `RATE_LIMIT_WINDOW_SECONDS` | `300` | Default 300. |
| `TRUST_PROXY_HEADERS` | `true` | Behind Render's proxy, limits each visitor by `X-Forwarded-For` instead of one shared bucket. |

**CORS details that break deployments:**

- The origin is scheme + host only: `https://your-project.vercel.app`, not
  `https://your-project.vercel.app/` and not `https://www.…` unless that is the URL people use.
- Preview deployments get a different URL on every push, so they will never match;
  they use the frontend's built-in proxy instead (see step 2).
- Changing environment variables on Render triggers a redeploy; wait for it to go live
  before testing.
- Optional: to show the dashboard's "requests left" indicator in production, add
  `expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"]` to the
  `CORSMiddleware` in `backend/app/main.py`. Without it, everything else still works.

**Free-tier cold start.** Free instances spin down after about 15 minutes without
traffic, and the next request takes roughly 50 seconds while they start. The dashboard
shows a "waking up" notice after 5 seconds, so nothing looks broken. Before a demo or
judging session, open `https://nasa-challenge-backend-nil7.onrender.com/health` a minute
ahead. To keep it awake, an external monitor (e.g. UptimeRobot) can request `/health`
every 10 minutes; that uses about 720 of the 750 free instance hours per month, so only
do it if this is the account's only free service.

## 2. Frontend on Vercel

1. **Add New… → Project**, then import `nasa-space-challenge-detector-system` from GitHub.
2. **Root Directory:** click **Edit** and choose `frontend`. The framework preset
   detects **Next.js**; leave the build, output and install commands at their defaults.
3. **Node.js version:** 22.x (the default; Next.js 16 needs 20.9 or newer).
4. **Environment Variables:**

   | Variable | Value | Environments |
   | --- | --- | --- |
   | `NEXT_PUBLIC_API_URL` | `https://nasa-challenge-backend-nil7.onrender.com` | Production only |
   | `BACKEND_URL` | `https://nasa-challenge-backend-nil7.onrender.com` | Preview (and Development, if you use `vercel dev`) |

   Use the FastAPI root: no trailing slash and no `/api`. An invalid value stops the
   build with a clear error message.
5. **Deploy**, then copy the production domain (e.g. `https://your-project.vercel.app`).
6. Send that origin to the backend owner for `CORS_ORIGINS` (step 1).
7. Put the URL in the README's "Live dashboard" row.

**How the frontend picks a backend.** In production builds with `NEXT_PUBLIC_API_URL`,
the browser calls that URL directly. Everywhere else (local development, preview
deployments) requests go to the site's own `/api/*`, which Next.js forwards server-side to
`BACKEND_URL`, so CORS never applies there.

**Build-time variables.** `NEXT_PUBLIC_*` values are compiled into the JavaScript during
`next build`, and the `/api` proxy target is fixed at build time too. Changing a variable
has no effect on existing deployments: redeploy (**Deployments → ⋯ → Redeploy**) after
every change.

## 3. Verify

1. Open `https://nasa-challenge-backend-nil7.onrender.com/health`; expect
   `{"status":"ok", …}` (this also wakes the server).
2. Open the dashboard. The chart and trend card load (after the "waking up" notice on a
   cold start).
3. In DevTools → **Network**, requests go to
   `https://nasa-challenge-backend-nil7.onrender.com/api/analysis?…` with status 200, and the
   **Console** shows no CORS errors.
4. Switch between Arctic and Antarctic; reloading the page shows cached results instantly.
5. The AI insight card shows an explanation, or a countdown if the rate limit was hit.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Console: "blocked by CORS policy" | `CORS_ORIGINS` doesn't match the site's origin exactly, or Render hasn't finished redeploying. |
| "Can't reach the analysis service" | Backend asleep or down. Open `/health`, wait, retry. |
| Production requests go to `your-project.vercel.app/api/...` | `NEXT_PUBLIC_API_URL` wasn't set when the deployment was built. Set it for Production and redeploy. |
| Build fails: "must point to the FastAPI root" | Remove the trailing `/api` from the URL. |
| Render fails at startup: "CORS_ORIGINS must be configured" | `APP_ENV=production` requires `CORS_ORIGINS`. |
| "Taking a short breather" countdown | Rate limit reached. It retries automatically; raise `RATE_LIMIT_REQUESTS` if judges share a network. |
| AI insight: "explanations aren't configured" | Set `GROQ_API_KEY` on Render. |
| AI insight: "explanation was rejected" | The backend's safety check refused the model's wording. Click **Regenerate**. |
