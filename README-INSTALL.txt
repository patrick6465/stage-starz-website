STAGE STARZ COMMAND CENTER V1

REPLACE:
- app.py
- templates/admin.html
- templates/media.html

ADD:
- templates/dashboard.html

The existing templates/store.html is included as a matching backup but does not
need to be replaced if your current store is working correctly.

INSTALL:
git checkout railway-deployment
git add app.py templates/admin.html templates/media.html templates/dashboard.html
git commit -m "Add Stage Starz Command Center"
git push origin railway-deployment

ROUTES:
- /admin          New Command Center
- /admin/store    Store Manager
- /admin/media    Media Library
- /               Main website
- /store          Customer storefront

This version uses the existing products database and does not delete or reset data.
