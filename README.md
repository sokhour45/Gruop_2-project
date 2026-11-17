# Gruop_2-project

A warehouse management system converted to a web application while keeping the same Python business logic and database model.

## Run the web app

```bash
python main.py
```

Then open http://127.0.0.1:5000 in a browser.

On first launch, create the administrator account. After that, the app keeps the same warehouse features as the original Python desktop version:

- Dashboard and stock summaries
- Product management
- Stock in and stock out records
- Transaction history
- CSV exports
- User role management for admin accounts

### Deploying the Flask app to Vercel

The Flask app uses SQLite locally, but Vercel's function filesystem is read-only
and ephemeral. Attach a persistent PostgreSQL database to the Vercel project and
make its connection URL available as `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`,
`DATABASE_URL`, or `WAREHOUSE_DATABASE_URL`. The Flask app creates its tables
on startup and stores registrations and warehouse data in PostgreSQL. Do not
point a deployed app at the repository's `warehouse.db`; it is not writable or
persistent on Vercel. Redeploy after setting the database environment variable.

The original Tkinter code remains available under the `warehouse/` package for reference.

See the [WMS Design](WMS_DESIGN.md) for the product scope, target architecture,
data model, warehouse workflows, integration outline, and phased roadmap.

See the [WMS Requirements](WMS_REQUIREMENTS.md) for user stories, acceptance
criteria, role definitions, priorities, and non-functional requirements.

See the [PostgreSQL Schema](WMS_POSTGRES_SCHEMA.md) for the target relational
schema, ledger rules, reconciliation, and concurrency guidance.

See the [WMS API Plan](WMS_API_PLAN.md) for REST endpoints, examples, validation,
authorization, transaction rules, and implementation phases.

See the [WMS UI Specification](WMS_UI_SPEC.md) for screen designs, navigation,
table columns, form validation, and layout guidance.

See the [Mobile UX Specification](WMS_MOBILE_UX_SPEC.md) for handheld workflows,
scan behavior, validation, offline handling, and PWA recommendations.

See the [WMS Process Logic](WMS_PROCESS_LOGIC.md) for workflow state machines,
scan validation, discrepancy handling, reservations, FEFO, and edge cases.

See the [WMS Analytics Specification](WMS_ANALYTICS_SPEC.md) for report
definitions, KPI formulas, dashboard recommendations, and data prerequisites.

See the [WMS Implementation Options](WMS_IMPLEMENTATION_OPTIONS.md) for a
build-vs-buy comparison, planning estimates, hardware kit, and recommendation.

See the [Updated WMS Project Plan](WMS_PROJECT_PLAN.md) for the scope baseline,
end-to-end status/posting rules, phased plan, backlog, KPIs, and open decisions.

See the [WMS Roadmap](WMS_ROADMAP.md) for the detailed rollout, training, pilot,
risks, and go-live readiness checklist that supports the updated project plan.

See the [WMS Test Cases](WMS_TEST_CASES.md) for barcode, workflow, ledger,
RBAC, and concurrency acceptance coverage.

## Django WMS MVP

The new MVP lives in `wms_backend/` and runs alongside the original Flask app.
It uses Django REST Framework, PostgreSQL (or SQLite for a quick local check),
JWT authentication, and a responsive PWA. The original Flask browser app remains available with `python main.py` at
<http://127.0.0.1:5000/>; its navigation and screens use the same local SVG
icons. The Django/PWA app is a separate app started with
`python wms_backend\manage.py runserver` at <http://127.0.0.1:8000/>.

### Local setup (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DJANGO_DEBUG = "true"
$env:DJANGO_SECRET_KEY = "local-only-change-this"
$env:WMS_ADMIN_PASSWORD = "ChangeThisLocalPassword123!"
python wms_backend\manage.py migrate
python wms_backend\manage.py seed_demo
python wms_backend\manage.py runserver
```

Open <http://127.0.0.1:8000/>. The seeded administrator is `admin`; the
password comes from `WMS_ADMIN_PASSWORD`. Choose a unique password for any
non-local installation.

### PostgreSQL

Copy `.env.example` to `.env`, replace the placeholder passwords and Django
secret, then start PostgreSQL with `docker compose up -d db`. In PowerShell,
load the values needed by Django from `.env` (or set them in the shell) before
running `manage.py migrate`, `seed_demo`, and `runserver`. Set
`DATABASE_URL` to the PostgreSQL URL shown in `.env.example`. The database
container persists data in the `wms-postgres-data` volume.

### Tests and key commands

```powershell
$env:DJANGO_DEBUG = "true"
$env:DJANGO_SECRET_KEY = "local-test-secret"
python wms_backend\manage.py check
python wms_backend\manage.py makemigrations --check --dry-run
python wms_backend\manage.py test warehouse_api
```

The API is rooted at `/api/v1/`; obtain and refresh JWTs at
`/api/v1/token/` and `/api/v1/token/refresh/`. The service worker only caches
the app shell; it does not queue or replay offline stock transactions. Use
stable warehouse Wi-Fi for all stock-changing operations. Operators can use
the Bin Transfer screen to scan-move available stock between storage bins;
each transfer writes balanced ledger entries and rejects reserved or
insufficient stock.
