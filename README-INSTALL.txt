STAGE STARZ CRM 2.0 — TIMELINE, TAGS & GLOBAL SEARCH

REPLACE:
- app.py
- database.py
- templates/customers.html
- templates/customer_profile.html
- templates/search.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/customers.html templates/customer_profile.html templates/search.html
git commit -m "Upgrade Stage Starz CRM timeline and search"
git push origin railway-deployment

FEATURES:
- Customer tag filters
- Customer status filters
- Tag shortcut buttons on profiles
- Unified timeline combining orders and notes
- Global search now finds customers and orders
- Customer lifetime value in search
- Order number, customer name, and email search
- Existing PostgreSQL customer schema migration retained
- Startup-safe customer backfill retained
- /health and /ready behavior unchanged

VERIFY:
1. Railway becomes Active.
2. /health returns ok.
3. /ready returns ready.
4. Open /admin/customers.
5. Add tags to a profile and filter by them.
6. Add a note and verify it appears in the timeline.
7. Search a customer name or order number from /admin/search.
