STAGE STARZ POSTGRESQL MIGRATION V1

REPLACE:
- app.py
- requirements.txt
- templates/dashboard.html

ADD:
- templates/database_status.html

INSTALL:
git checkout railway-deployment
git add app.py requirements.txt templates/dashboard.html templates/database_status.html
git commit -m "Migrate Stage Starz data to PostgreSQL"
git push origin railway-deployment

RAILWAY WEBSITE SERVICE SETUP:
1. Open the stage-starz-website service.
2. Open Variables.
3. Click New Variable or Add Reference.
4. Add a reference to the Postgres service variable DATABASE_URL.
5. The website service should then show DATABASE_URL as a referenced variable.
6. Redeploy the website service.

VERIFY:
Open /admin/system/database.
It must say: PostgreSQL connected.

IMPORTANT:
PostgreSQL stores products, orders, homepage settings, announcements, reports,
and activity records. Uploaded images still require persistent file storage.
Keep UPLOAD_FOLDER pointed to a volume such as /data/uploads if image persistence
is needed.

The code retains SQLite only as a local-development fallback when DATABASE_URL
is absent.
