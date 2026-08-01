STAGE STARZ CRM — CUSTOMERS V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/customers.html
- templates/customer_profile.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/customers.html templates/customer_profile.html
git commit -m "Add Stage Starz customer CRM"
git push origin railway-deployment

WHAT THIS ADDS:
- PostgreSQL customers table
- PostgreSQL customer_notes table
- Automatic backfill from existing non-cancelled orders
- Automatic customer creation and updates after every new order
- Customer totals refresh after order status changes
- Searchable and sortable Customers page
- Customer lifetime value and order counts
- Customer profile pages
- Editable name, phone, status, tags and profile notes
- Dated customer note history
- Linked order history
- Customers navigation in Command Center

OPEN:
- /admin/customers

VERIFY:
1. Railway deployment is Active.
2. /health passes.
3. /ready reports PostgreSQL ready.
4. /admin/customers shows customers created from existing orders.
5. Open a customer and confirm their linked order history.
