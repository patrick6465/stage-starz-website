STAGE STARZ RECITAL MANAGEMENT V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/recital_center.html
- templates/recital_production.html
- templates/recital_show.html

CONFIRM PRESENT:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/admin_login.html templates/recital_center.html templates/recital_production.html templates/recital_show.html
git commit -m "Add Stage Starz recital management"
git push origin railway-deployment

V1 FEATURES:
- Recital productions
- Multiple shows per production
- Show dates, times, doors-open time, venue, and status
- Performance lineups
- Class-to-performance assignment
- Active student counts from class rosters
- Music title, URL, and readiness status
- Entrance, exit, and costume notes
- Performance duration and type
- Move performances up and down
- Rehearsal scheduling
- Workflow events for productions, shows, performances, and rehearsals
- Owner and Office Staff access
- Migration Center milestone 014

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Migration Center shows Recital Management Center.
5. Open /admin/recitals.
6. Create a production.
7. Add a show.
8. Add performances and assign classes.
9. Move performances up and down.
10. Add music status and a rehearsal.
11. Confirm recital events appear in Workflow Center.
