STAGE STARZ MIGRATION CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/migration_center.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/migration_center.html
git commit -m "Add Stage Starz Migration Center"
git push origin railway-deployment

FEATURES:
- schema_migrations history table
- Seven registered migration milestones
- Applied, verified, and attention-required states
- Required table verification
- Required column verification
- PostgreSQL/SQLite table inventory
- Record counts by table
- Column names and database types
- Manual Run Verification button
- Migration history timestamps
- Command Center navigation link

SAFETY:
- No heavy migration work during Railway startup
- Verification is read-only except recording healthy migration history
- Existing business data is never deleted or rewritten
- /health and /ready remain unchanged

OPEN:
- /admin/system/migrations

VERIFY:
1. Railway becomes Active.
2. /health returns ok.
3. /ready returns ready.
4. Open Migration Center.
5. All seven migrations should show Applied or Verified.
6. Any missing schema component will be displayed under Attention Required.
