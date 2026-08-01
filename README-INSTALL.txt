STAGE STARZ COMMAND CENTER 2.0 — LIVE OPERATIONS DASHBOARD

REPLACE:
- app.py
- templates/dashboard.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html
git commit -m "Upgrade Command Center to live PostgreSQL dashboard"
git push origin railway-deployment

WHAT THIS ADDS:
- Personalized time-based greeting
- Sales today
- Sales this month
- Total and new orders
- Processing and ready-order counts
- Current inventory value
- Low-stock and out-of-stock alerts
- Active announcement count
- Recent orders
- Recent activity
- PostgreSQL connection indicator
- Improved mobile navigation
- Faster links to Orders, Store, Homepage, Announcements, Reports, and Media

This upgrade uses the same Railway PostgreSQL database already connected to the
public website, store, and Command Center. It does not create a second database.
