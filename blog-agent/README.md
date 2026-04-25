# Buteforce Blog Agent

Stateful AI pipeline for blog creation:

1. Research
2. Verify research
3. Write and humanize draft
4. Verify draft
5. Publish

The dashboard (`dashboard/`) triggers Python orchestration (`run.py`) through API routes.

## Local run

Prerequisites:

- Node 20+
- Python 3.10+

Install:

```powershell
cd blog-agent
python -m pip install -r requirements.txt
cd dashboard
npm ci
```

Environment:

- Copy `.env.example` to `.env` in `blog-agent/`
- Copy `.env.example` to `dashboard/.env.local` (or map only required keys)

Runtime visibility:

- The browser console will not show Python pipeline logs. `run.py` runs on the server, so raw stdout/stderr appears in server logs.
- The dashboard should show pipeline status changes in-app. For production debugging, check the Render service logs.

Start dashboard:

```powershell
cd blog-agent/dashboard
npm run dev
```

Dashboard endpoints:

- `POST /api/run`
- `POST /api/approve`
- `POST /api/reject`
- `GET /api/topics`
- `GET /api/topic/:slug`

## Production notes

- Dashboard API routes spawn `python run.py`; deploy target must support both Node and Python in the same runtime.
- Do not expose `SUPABASE_SERVICE_KEY` to browser code.
- Keep `PUBLISH_DRY_RUN=true` until GitHub publishing credentials are verified.

## Render

Use the blueprint in `render.yaml`.

Expected health check:

- `/`
