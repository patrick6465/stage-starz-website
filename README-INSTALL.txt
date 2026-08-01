STAGE STARZ POSTGRESQL STARTUP FIX

WHY THE PAGE WAS MISSING:
The first PostgreSQL app.py omitted MAX_IMAGE_BYTES and
ALLOWED_IMAGE_EXTENSIONS. That caused the new Railway deployment to fail during
startup. Railway therefore continued serving the previous working deployment,
which did not contain /admin/system/database.

REPLACE:
- app.py

INSTALL:
git checkout railway-deployment
git add app.py
git commit -m "Fix PostgreSQL application startup"
git push origin railway-deployment

THEN:
1. Open the stage-starz-website service in Railway.
2. Open Deployments.
3. Wait until the newest deployment says Active or Success.
4. If it says Failed, open View Logs and copy the first red error.
5. Open /admin/system/database.

EXPECTED RESULT:
- Logged out: redirected to /admin/login
- Logged in with DATABASE_URL connected: PostgreSQL connected
