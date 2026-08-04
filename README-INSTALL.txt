STAGE STARZ RESERVED TICKETING V1.5

REPLACE:
- app.py
- database.py
- templates/ticket_venue.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/ticket_venue.html
git commit -m "Add Meyer Theater preset and advanced venue objects"
git push origin railway-deployment

V1.5:
- One-click Meyer Theater starter preset
- Main orchestra rows with stage-right low-number display
- Row X accessible wheelchair spaces
- Row X companion seats
- Row X soft seating
- Rear-center theater crew booth
- Vertical upper VIP left section
- Vertical upper VIP right section
- Rear horizontal VIP seating
- Round VIP guest-table objects
- Custom theater-object editor
- Objects can represent VIP tables, booths, labels, aisles, or exits
- Preset remains fully editable until tickets exist
- Workflow event when a preset is applied
- Migration Center milestone 017 expanded

IMPORTANT:
- The preset is an editable starter constructed from the supplied Meyer Theater chart.
- Review the exact seat endpoints and Row X quantities against the venue's final official chart before ticket sales.
- The round VIP tables are physical guest tables and are not themselves selectable tickets.
- The VIP chairs remain the ticketed seats.

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Create an empty venue called Meyer Theater.
5. Click Apply Meyer Theater Preset.
6. Confirm the main rows, Row X, VIP sections, booth, and round tables appear.
7. Adjust any seat endpoints that differ from the final theater chart.
8. Confirm Row X seat types include Accessible, Companion, and Soft Seating.
9. Confirm ticket sales still work after assigning the venue to a show.
