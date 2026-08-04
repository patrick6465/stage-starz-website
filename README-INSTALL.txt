STAGE STARZ PUBLIC RESERVED TICKET SALES PORTAL V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html
- templates/ticket_show.html

ADD:
- templates/public_ticket_portal.html
- templates/public_ticket_show.html
- templates/public_ticket_checkout.html
- templates/public_ticket_order.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/ticket_show.html templates/public_ticket_portal.html templates/public_ticket_show.html templates/public_ticket_checkout.html templates/public_ticket_order.html
git commit -m "Add public reserved ticket sales portal"
git push origin railway-deployment

VERIFY:
1. Railway Active.
2. /health and /ready pass.
3. Migration Center shows 018_public_ticket_sales.
4. Open an admin ticket show and enable Public Ticket Sales.
5. Open /tickets.
6. Select seats and complete a Pay at Studio order.
7. Test Family Billing with a family account.
8. Confirm temporary seat locks and printable ticket codes.
