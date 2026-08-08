STAGE STARZ RECITAL PRODUCTION CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/production_center.html
- templates/production_show.html
- templates/production_performance.html
- templates/production_live.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/production_center.html templates/production_show.html templates/production_performance.html templates/production_live.html
git commit -m "Add recital production center"
git push origin railway-deployment

VERIFY:
1. Railway Active
2. /health ok
3. /ready ready
4. Migration Center shows 019
5. Open /admin/production
6. Open a recital show and sync class dancers
7. Add cues, dressing rooms, quick changes, volunteers, and checklist items
8. Open Live Stage Manager and advance performances
