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

## Deploy to Vercel

Vercel functions cannot persist writes to the app's local `warehouse.db`. For
a Vercel deployment, create a Turso database and add these environment
variables in the Vercel project's **Settings > Environment Variables**:

- `TURSO_DATABASE_URL` — the database URL from Turso.
- `TURSO_AUTH_TOKEN` — an auth token for that database.

Redeploy after saving the variables. The app creates its tables in Turso on
startup; on a new database, create the first administrator account from the
login page. The local `warehouse.db` is still used when running outside Vercel
without Turso variables. Its existing data is not automatically copied to
Turso.

The original Tkinter code remains available under the `warehouse/` package for reference.