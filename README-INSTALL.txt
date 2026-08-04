STAGE STARZ COMPETITION MANAGEMENT V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/competition_center.html
- templates/competition_profile.html
- templates/competition_routine.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/competition_center.html templates/competition_profile.html templates/competition_routine.html
git commit -m "Add Stage Starz competition management"
git push origin railway-deployment

FEATURES:
- Competition events, venues, dates, and deadlines
- Hotel, travel, website, and planning notes
- Routines linked to classes, recital performances, and costumes
- Automatic dancer assignment from active class enrollment
- Music, entry, performance time, and stage tracking
- Entry-fee billing integration
- Registration, waiver, travel, and costume readiness
- Awards, placements, scores, and judge notes
- Workflow events
- Migration Center milestone 016

VERIFY:
1. Railway Active
2. /health ok
3. /ready ready
4. Migration Center shows Competition Management
5. Create a competition
6. Add a routine linked to a class
7. Confirm dancers auto-populate
8. Update a dancer and create a test fee charge
9. Record a test award
10. Confirm workflow events
