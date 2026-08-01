STAGE STARZ COMMAND CENTER V2

REPLACE:
- app.py
- templates/dashboard.html
- templates/admin.html

ADD:
- templates/search.html

KEEP your existing store.html and media.html unless you deliberately want to replace them.

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/admin.html templates/search.html
git commit -m "Upgrade Stage Starz Command Center"
git push origin railway-deployment

NEW FEATURES:
- Expandable module navigation
- Global search for products, website pages, and uploaded media
- Notification drawer
- Administrator profile drawer
- Quick-create panel
- Automatic recent activity log
- Inventory alert cards
- Responsive mobile navigation

DATABASE:
A new activity_log table is added automatically. Existing products and settings are preserved.
