# NASA Sea-Ice Backend

FastAPI backend for the NASA sea-ice trend application.

The backend loads the bundled NASA CSV exports, validates and aggregates the
monthly observations, computes the statistical result in Python, and exposes
that result through FastAPI. The AI endpoint only explains an already-calculated
result; it is not part of the statistical calculation path.

## Run locally

From this directory, create and activate a virtual environment, install the
dependencies, and start the development server:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set GROQ_API_KEY to your local secret.
python -m uvicorn app.main:app --reload
```

API requests are rate-limited per client IP to 10 requests per 5 minutes by
default. Override this with `RATE_LIMIT_REQUESTS` and
`RATE_LIMIT_WINDOW_SECONDS`. A limited request returns HTTP 429 with
`code: "RATE_LIMIT_EXCEEDED"`, a user-facing `message`, and
`retry_after_seconds` for the frontend.

CORS always allows the project's own frontends: `http://localhost:3000`,
`http://127.0.0.1:3000`, `http://localhost:5173` and the deployed dashboard
`https://environmental-analytics-dashboard.vercel.app`. Add more exact origins
(comma-separated, no trailing slash, no `*`), such as a custom domain, with the
`CORS_ORIGINS` environment variable. Set `APP_ENV=production` in deployment;
production startup requires `CORS_ORIGINS` to be set.
Responses expose `Retry-After` and the `X-RateLimit-*` headers to the browser,
and CORS preflight requests never count against the rate limit.

Behind a proxy such as Render's, set `TRUST_PROXY_HEADERS=true` so each visitor
is limited by their own address (the first `X-Forwarded-For` entry) instead of
sharing one budget. The limiter forgets inactive clients and tracks at most
10,000 at a time.

## AI explanations

`POST /api/explain` accepts a Python-calculated `region`, `variable`, `period`,
and `trend` result. The backend sends it to Groq's
`openai/gpt-oss-120b` model to write a concise explanation. The API key
is loaded only by the backend and is never part of the frontend request or
response. The AI layer does not calculate or modify statistical results.

Example request:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/explain `
  -ContentType 'application/json' -Body (@{
    region = 'arctic'
    variable = 'sea_ice_fraction'
    period = @{ start = 1948; end = 2025 }
    trend = @{
      direction = 'decreasing'
      sen_slope = -0.0018
      p_value = 0.002
      significant = $true
    }
  } | ConvertTo-Json -Depth 4)
```

The response has the form `{ "explanation": "..." }`. The server sends the
validated JSON to Groq as text through the official `groq` SDK; it
does not send or process an image for this endpoint.

Every reply is checked before it is returned. It must state the supplied
direction and significance and must not claim causes such as climate change.
It may quote only numbers from the result, rounded or written in another
common notation (`1.5 × 10⁻¹⁰`, a dropped minus sign), plus conventional
significance levels that the p-value supports (`p < 0.001`, `95%`). A rejected
reply is retried with the reason, up to 3 Groq calls within 45 seconds.
Temporary Groq failures are retried with exponential backoff and jitter,
following Groq's `Retry-After`. `GROQ_TIMEOUT_SECONDS` (default 20) limits each
call.

| Status | Meaning |
|---|---|
| 429 | Groq is rate-limiting the server. `Retry-After` says when to retry (at most 60 seconds). |
| 502 | No reply passed the checks, or Groq returned an error or could not be reached. |
| 503 | `GROQ_API_KEY` is missing, or Groq rejected the key, model or request parameters. |
| 504 | Groq did not answer in time. |

Each problem is logged to stdout with the reason: `Explanation rejected:` with
the model's reply, `Explanation upstream error:` with Groq's own error
message, and `Explanation failed:` with the status returned.

## Tests

Install the development dependencies and run the integration tests from this
directory:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## API endpoints

- `GET /` — basic service status
- `GET /health` — health check
- `GET /api/regions` — supported regions
- `GET /api/variables` — supported variables
- `GET /api/series?region=arctic` — validated monthly observations
- `GET /api/trend?region=arctic` — Python-calculated trend result
- `GET /api/analysis?region=arctic` — annual series plus trend result
- `GET /api/trends` — trend-analysis implementation status
- `POST /api/explain` — concise explanation of a supplied calculated result
- `/docs` — FastAPI interactive documentation

The API returns the period represented by complete annual observations. A
partial year is retained in the monthly series but excluded from annual trend
analysis.
