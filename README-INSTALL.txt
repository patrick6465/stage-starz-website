STAGE STARZ ORDERS DASHBOARD V1

REPLACE:
- app.py
- templates/dashboard.html
- templates/store.html

ADD:
- templates/orders.html
- templates/order_detail.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/store.html templates/orders.html templates/order_detail.html
git commit -m "Add orders dashboard"
git push origin railway-deployment
