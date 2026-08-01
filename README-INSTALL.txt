STAGE STARZ RAILWAY HEALTH CHECK FIX

CAUSE:
Railway was checking /health during deployment. The cleanup version made
/health depend on PostgreSQL. A temporary database delay returned HTTP 503,
so Railway marked the web deployment unhealthy even when Gunicorn was running.

REPLACE:
- app.py
- database.py

INSTALL:
git checkout railway-deployment
git add app.py database.py
git commit -m "Fix Railway health and readiness checks"
git push origin railway-deployment

RAILWAY SETTINGS:
Service Settings -> Healthcheck Path:
  /health

DO NOT use /ready as the deployment healthcheck.

ENDPOINTS:
- /health returns HTTP 200 when the web server is running.
- /ready checks PostgreSQL and returns detailed readiness information.
- PostgreSQL connections now time out after 5 seconds instead of hanging.

VERIFY:
1. New Railway deployment becomes Active.
2. Open /health: status should be ok.
3. Open /ready: status should be ready and backend postgresql.
4. Open /admin and /admin/orders.
