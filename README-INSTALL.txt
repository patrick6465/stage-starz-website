STAGE STARZ FAMILY FOUNDATION V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/families.html
- templates/family_profile.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/families.html templates/family_profile.html
git commit -m "Add Stage Starz family foundation"
git push origin railway-deployment

FEATURES:
- PostgreSQL families table
- PostgreSQL family_notes table
- Safe family_id migration on existing customers
- Automatic family creation from customer name, email, and phone
- Existing customers assigned to families when Families opens
- New order customers automatically linked to families
- Family metrics: members, orders, lifetime value, last activity
- Searchable family list
- Family profile with members, orders, notes, tags, and timeline
- Command Center Families navigation

STARTUP SAFETY:
- No family backfill runs during Railway startup
- /health and /ready remain unchanged
- Family assignment errors are logged without taking the site offline

VERIFY:
1. Railway deployment becomes Active.
2. /health returns ok.
3. /ready returns ready.
4. Open /admin/families.
5. Existing customers should be assigned to family records.
6. Open a family and verify members and orders.
