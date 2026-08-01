STAGE STARZ PERSISTENT DATABASE FIX

REPLACE:
- app.py
- templates/dashboard.html

ADD:
- templates/storage_status.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/storage_status.html
git commit -m "Fix persistent Railway database storage"
git push origin railway-deployment

RAILWAY:
1. Attach a volume to the SAME Stage Starz service.
2. Set the volume mount path to /data.
3. Recommended variables:
   DATABASE_PATH=/data/store.db
   UPLOAD_FOLDER=/data/uploads

VERIFY:
Open /admin/system/storage.
It must say: Persistent storage is active.

IMPORTANT:
Orders created in an earlier ephemeral deployment may not be recoverable after
that deployment was replaced. This fix prevents future orders from disappearing.
