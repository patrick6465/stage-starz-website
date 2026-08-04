STAGE STARZ RESERVED SEATING & TICKETING V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/ticketing_center.html
- templates/ticket_venue.html
- templates/ticket_show.html
- templates/ticket_order.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/ticketing_center.html templates/ticket_venue.html templates/ticket_show.html templates/ticket_order.html
git commit -m "Add Stage Starz reserved seating ticketing"
git push origin railway-deployment

V1 FEATURES:
- Reserved seating only
- Reusable venue layouts
- Sections, rows, seat numbers, and seat types
- Standard, VIP, Accessible, and Companion seats
- Show-specific seat maps
- Available, held, sold, complimentary, voided, and checked-in states
- Family-linked and walk-up ticket orders
- Ticket pricing and payment status
- Optional family billing charge
- Unique printable ticket codes
- Printable individual tickets
- Door check-in
- Voiding releases seats
- Workflow events
- Owner, Office Staff, and Store Manager access
- Migration Center milestone 017

NOT INCLUDED YET:
- Public online seat purchasing
- Credit-card processing
- QR image generation or camera scanning
- Refund payment-provider integration

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Migration Center shows Reserved Seating and Ticketing Center.
5. Open /admin/ticketing.
6. Create a venue.
7. Generate at least one seating section.
8. Open a recital show and assign the venue.
9. Set a default price and sales status.
10. Select seats and create a test order.
11. Print tickets and test check-in.
12. Void the test order and confirm seats become available.
