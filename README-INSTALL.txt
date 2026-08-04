STAGE STARZ RESERVED TICKETING V1.9

REPLACE:
- app.py

INSTALL:
git checkout railway-deployment
git add app.py
git commit -m "Correct Meyer Row X to seats 101 through 130"
git push origin railway-deployment

ROW X CORRECTION:
- Row X remains between Upper Orchestra and Lower Orchestra.
- Row X now contains:
  * One soft-seat position on the left
  * Numbered seats 101 through 130
  * One soft-seat position on the right
- 30 numbered seats
- 2 soft-seat positions
- 32 total positions
- Row X width increased to fit the complete sequence.

IMPORTANT:
Existing Meyer preset data will not update automatically.
1. Deploy V1.9.
2. Open the unfinished Meyer Theater venue.
3. Reset Seating Chart.
4. Apply the Coordinate-Based Meyer Preset again.
5. Confirm Row X displays:
   Soft Seat · 101–130 · Soft Seat
