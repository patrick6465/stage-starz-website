STAGE STARZ CODEBASE CLEANUP V1

This is a safe structural cleanup. It does not intentionally change the public
website, store, orders, reports, announcements, or Command Center behavior.

REPLACE:
- app.py
- requirements.txt

ADD:
- config.py
- database.py
- templates/500.html
- stage_starz/__init__.py

INSTALL:
git checkout railway-deployment
git add app.py config.py database.py requirements.txt templates/500.html stage_starz/__init__.py
git commit -m "Clean up Stage Starz application architecture"
git push origin railway-deployment

WHAT CHANGED:
- Environment and path settings moved into config.py
- PostgreSQL/SQLite connection logic moved into database.py
- Database initialization and schema migrations moved out of app.py
- app.py now focuses on routes and business workflows
- Central application logging added
- /health now tests the actual database connection
- Friendly 500 error page added
- stage_starz package created for future route and service modules
- PostgreSQL remains the production database
- SQLite remains only as a local-development fallback

VERIFY AFTER DEPLOYMENT:
1. Railway deployment is Active.
2. Open /health and confirm:
   status=ok
   database=connected
   backend=postgresql
3. Open /admin.
4. Open /admin/orders and confirm existing orders.
5. Open /admin/system/database and confirm PostgreSQL connected.

The next cleanup pass can move Website, Commerce, Orders, and Admin routes into
separate Flask Blueprints after this version is verified.
