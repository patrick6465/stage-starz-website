STAGE STARZ PHASE 1 — MEDIA MANAGER

Replace/add these files in the railway-deployment branch:

REPLACE:
- app.py
- templates/admin.html
- templates/store.html

ADD:
- templates/media.html

Then run:
git checkout railway-deployment
git add app.py templates/admin.html templates/store.html templates/media.html
git commit -m "Start Phase 1 media manager"
git push origin railway-deployment

Railway will redeploy automatically.

Your existing /data volume is used for uploaded photos. Optional Railway variable:
UPLOAD_FOLDER=/data/uploads

This update adds:
- Direct product photo uploads
- Persistent Railway image storage
- Media Library at /admin/media
- Safe image deletion
- 10 MB image limit
- Existing color toggle support
- Automatic database migration with no product loss
