STAGE STARZ RESERVED TICKETING V1.3

REPLACE:
- app.py
- database.py
- templates/ticket_venue.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/ticket_venue.html
git commit -m "Add visual seating chart preview and row spacing"
git push origin railway-deployment

NEW:
- Visible auditorium-style seating chart preview
- Stage, sections, rows, and actual seat numbers
- Add extra space after any selected row
- Use spacing for aisles and walkways
- Optional aisle notes
- Layout locks after ticket history exists

TEST:
1. Open an unfinished venue.
2. Confirm preview appears.
3. Set Row A extra space to 35.
4. Save and confirm a larger gap before Row B.
5. Set it back to 0 to remove the gap.
