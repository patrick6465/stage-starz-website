STAGE STARZ RESERVED TICKETING V1.2

REPLACE:
- app.py
- templates/ticket_venue.html

INSTALL:
git checkout railway-deployment
git add app.py templates/ticket_venue.html
git commit -m "Improve reserved seating row builder"
git push origin railway-deployment

NEW ROW BUILDER:
- Build one row at a time.
- Enter the actual row label.
- Enter the actual first and last seat numbers.
- Example: Row A, seats 101 through 121.
- Reverse numbering is supported: 121 through 101.
- Re-enter the same section name to add another row to that section.
- Duplicate seats in the same section and row are skipped safely.
- Existing venue editing, deletion protection, seat holds, orders, and check-in remain unchanged.

TEST:
1. Open an unfinished venue.
2. Section: Orchestra Center
3. Row: A
4. First seat: 101
5. Last seat: 121
6. Confirm A-101 through A-121 are created.
7. Add Row B using the same section name.
8. Test a reverse-numbered row if the theater uses one.
