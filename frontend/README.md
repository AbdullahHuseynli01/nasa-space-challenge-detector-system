# NASA Environmental Analytics: Frontend

Minimal, claymorphic dashboard for NASA environmental time series: an annual chart,
the backend's statistical trend, and an AI explanation of that trend. Light and dark themes.

Next.js 16 (App Router) · TypeScript (strict) · Tailwind CSS 4 · TanStack Query 5 · Framer Motion · Lucide · Zod

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server on http://localhost:3000 |
| `npm run build` / `npm start` | Production build / serve it |
| `npm run lint` | ESLint (no `any`, no `!` assertions, explicit return types outside components) |
| `npm run typecheck` | Generates Next's route types, then `tsc --noEmit` |
| `npm run check` | Lint + typecheck, e.g. for CI |

## Configuration

Copy `.env.example` to `.env.local`. Values are read when `next dev` starts
(restart after changing them) and when `next build` runs.

| Variable | Purpose |
| --- | --- |
| `BACKEND_URL` | Target of the same-origin `/api/*` proxy: the FastAPI root, without `/api`. Defaults to `http://127.0.0.1:8000`. |
| `NEXT_PUBLIC_API_URL` | Production only: the browser calls this backend directly, so its `CORS_ORIGINS` must include the site. |
| `BACKEND_PROXY_TIMEOUT_MS` | Optional proxy timeout, default 130000 (AI explanations can be slow). |

How requests are routed (`src/lib/api/http.ts` and `next.config.ts` apply the same rule):

- **Development:** always the proxy, so CORS never applies locally. The target is
  `BACKEND_URL`, else `NEXT_PUBLIC_API_URL`, else the local backend.
- **Production:** direct to `NEXT_PUBLIC_API_URL` when it is set; otherwise the proxy
  (e.g. Vercel preview deployments).

Invalid URLs stop `next dev` / `next build` with a clear error. Switching backends
discards the browser's cached results from the old one.

## Project structure

```
src/
├── app/                          Routing shell
│   ├── layout.tsx                Fonts, metadata, no-flash theme script
│   ├── page.tsx                  <Suspense> + <Dashboard>
│   ├── providers.tsx             TanStack Query (persisted to localStorage) + MotionConfig
│   ├── globals.css               Clay design tokens, light and dark
│   └── icon.svg                  App icon
├── core/                         Domain configuration (no React)
│   ├── datasets/
│   │   ├── types.ts              VariableStrategy, DatasetDefinition, TrendMethodology
│   │   ├── define.ts             defineDataset / defineVariable (+ API and methodology defaults)
│   │   ├── sea-ice.ts            The sea-ice dataset
│   │   └── registry.ts           DATASET_REGISTRY → every id union, lookup and selection
│   ├── regions/
│   │   ├── define.ts             RegionDefinition, defineRegion, formatBounds
│   │   └── catalog.ts            Regions shared by several datasets (arctic, antarctic)
│   └── query/                    Query keys, query options, QueryClient + persistence
├── lib/                          Framework-agnostic logic
│   ├── api/                      HTTP client, zod schemas, typed errors, rate-limit gate, endpoints
│   ├── charts/series-geometry.ts Scales, paths and ticks for the series chart
│   ├── insights/parse-insight.ts Highlights the facts in the AI explanation
│   ├── sanitize/                 sanitizeFloat + Pydantic-safe trend payload
│   └── format.ts, theme.ts, cn.ts
├── hooks/                        URL-backed selection, queries, rate-limit countdown, slow-load flag, element size, hydration
├── components/
│   ├── ui/                       Clay primitives: ClayCard, ClayButton, Segmented, Skeleton, CountdownRing, ThemeToggle
│   ├── dashboard/                Dashboard layout, selectors, series card + chart, trend card
│   ├── insights/                 AiInsightCard, InsightText
│   └── feedback/                 ErrorState (incl. auto-retrying 429 countdown)
└── types/api.ts                  Wire contracts mirroring backend/app/models/schemas.py
```

## Adding a dataset

Two steps. Charts, cards, region and variable selectors, zod validation,
query keys and every id type are derived from the registry.

1. Define it, e.g. `src/core/datasets/co2.ts`. A new region can be declared right here:

   ```ts
   const globe = defineRegion({
     id: "global",
     label: "Global",
     bounds: { latMin: -90, latMax: 90, lonMin: -180, lonMax: 180 },
   });

   export const co2Dataset = defineDataset({
     id: "co2",
     label: "CO₂",
     description: "Atmospheric CO₂ trend analysis.",
     source: "NASA OCO-2",
     regions: [globe],
     variables: [
       defineVariable({
         id: "co2_concentration", // must match the backend's Variable enum
         unit: "ppm", // must match the backend's Unit enum
         unitLabel: "ppm",
         // labels, formatValue / formatTick / formatRate, domain, trendLabels…
       }),
     ],
   });
   ```

2. Add it to `DATASET_REGISTRY` in `src/core/datasets/registry.ts`.

Sea ice is the only dataset, so the dashboard has no dataset menu. A second dataset
also needs a menu that lets people choose it.

Optional per-dataset overrides: `api` (endpoint paths) and `methodology` (statistic
labels). The registry rejects two different objects with the same id, so shared
regions are imported from `core/regions/catalog.ts` instead of being redefined.

## Rate limits and caching

The backend allows only a few `/api/*` requests per window, so the app:

- never refetches implicitly (`staleTime: Infinity`, no retries, no focus refetch);
- caches AI insights under `[region, variable, startYear, endYear]` and persists
  successful results to `localStorage` for 24 hours;
- after a 429, blocks further requests locally until `retry_after_seconds` has
  passed, shows a countdown and retries automatically;
- explains a slow first load (a sleeping free-tier server) after 5 seconds instead of
  showing a silent skeleton.

## Deploying to Vercel

The app lives in `frontend/` of the monorepo (next to `backend/`) and is self-contained:
its own lockfile, and `next.config.ts` pins the project root to this folder. In Vercel,
set **Root Directory** to `frontend`, `NEXT_PUBLIC_API_URL` for Production and
`BACKEND_URL` for Preview. The full checklist, including the backend's CORS settings, is
in [DEPLOYMENT.md](../DEPLOYMENT.md).

To try a production build locally against the proxy, leave `NEXT_PUBLIC_API_URL` unset
(the default `.env.local` does).
