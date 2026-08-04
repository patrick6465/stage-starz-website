STAGE STARZ RESERVED TICKETING V1.6

REPLACE:
- app.py
- database.py
- templates/ticket_venue.html
- templates/ticket_show.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/ticket_venue.html templates/ticket_show.html
git commit -m "Add coordinate based theater canvas designer"
git push origin railway-deployment

NEW:
- True X/Y coordinate canvas
- Position, size, rotation, and layer for every seating section
- Position, size, rotation, layer, and shape for every theater object
- Circle VIP tables, rectangle stage/booth, label objects
- Meyer preset rebuilt with independent coordinates
- Same coordinates used by live ticket sales map
- Existing row direction, spacing, holds, orders, billing, and check-in remain

TEST:
1. Reset the unfinished Meyer chart.
2. Apply Coordinate Meyer Preset.
3. Move a section by changing X/Y.
4. Move a table or booth by changing X/Y.
5. Confirm the live recital sales map matches the venue preview.
