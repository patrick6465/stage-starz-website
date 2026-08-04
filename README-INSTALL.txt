STAGE STARZ RESERVED TICKETING V1.1

REPLACE:
- app.py
- database.py
- templates/ticket_venue.html
- templates/ticket_show.html

ADD:
- templates/ticket_hold.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/ticket_venue.html templates/ticket_show.html templates/ticket_hold.html
git commit -m "Add seat map editing and reserved seat holds"
git push origin railway-deployment

VERIFY:
- Edit/delete/reset unfinished seating charts
- Place, edit, release, and convert holds
- Confirm layouts lock after ticket history exists
