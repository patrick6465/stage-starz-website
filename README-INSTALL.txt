STAGE STARZ REPORTS & ANALYTICS V1

REPLACE:
- app.py
- templates/dashboard.html

ADD:
- templates/reports.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/reports.html
git commit -m "Add reports and analytics"
git push origin railway-deployment

OPEN:
- /admin/reports

REPORTS INCLUDED:
- Total revenue
- Valid order count
- Average order value
- Completed and cancelled orders
- Daily revenue chart
- Payment mix
- Order status breakdown
- Best-selling products
- Inventory value and units
- Low-stock alerts
