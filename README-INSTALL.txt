STAGE STARZ CODEBASE CLEANUP V1 — DEPLOYMENT FIX

The first cleanup package accidentally copied Flask application setup into
database.py. Railway failed during startup because database.py tried to call
Flask without importing it.

REPLACE:
- app.py
- database.py

If the other cleanup files were never deployed, also add:
- config.py
- templates/500.html
- stage_starz/__init__.py
- requirements.txt

RECOMMENDED COMMAND:
git checkout railway-deployment
git add app.py database.py config.py requirements.txt templates/500.html stage_starz/__init__.py
git commit -m "Fix codebase cleanup deployment"
git push origin railway-deployment

VERIFY:
1. Railway deployment becomes Active.
2. Open /health.
3. Confirm status=ok, database=connected, backend=postgresql.
4. Open /admin and /admin/orders.
