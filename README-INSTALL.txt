STAGE STARZ CRM V1 — STARTUP-SAFE FIX

WHY THE DEPLOYMENT FAILED:
The CRM tried to backfill all customers while the application was starting.
If that SQL operation failed for any reason, Gunicorn never opened the network
port and Railway reported a network health-check failure.

REPLACE:
- app.py
- database.py

INSTALL:
git checkout railway-deployment
git add app.py database.py
git commit -m "Make CRM customer migration startup safe"
git push origin railway-deployment

HOW THIS VERSION WORKS:
- Startup only creates the customers and customer_notes tables.
- The web server becomes healthy before any CRM data backfill runs.
- Existing orders are converted into customers when /admin/customers opens.
- A backfill error is logged but cannot take the website offline.
- New orders still create or update customers automatically.

VERIFY:
1. Railway deployment becomes Active.
2. /health returns status ok.
3. /ready returns status ready.
4. Open /admin.
5. Open /admin/customers and confirm existing order customers appear.
