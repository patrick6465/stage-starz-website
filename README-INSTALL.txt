STAGE STARZ DIGITAL TICKET DELIVERY & DOOR CHECK-IN V1

REPLACE:
- app.py
- database.py
- requirements.txt
- templates/ticket_show.html
- templates/public_ticket_order.html
- templates/ticket_order.html

ADD:
- templates/ticket_checkin_center.html
- templates/mobile_ticket.html

INSTALL:
git checkout railway-deployment
git add app.py database.py requirements.txt templates/ticket_show.html templates/public_ticket_order.html templates/ticket_order.html templates/ticket_checkin_center.html templates/mobile_ticket.html
git commit -m "Add digital QR tickets and door checkin"
git push origin railway-deployment

FEATURES:
- Real QR image on every mobile ticket
- Mobile-friendly ticket page
- Door Check-In Center per show
- Camera QR scanning when browser BarcodeDetector is available
- Manual lookup fallback by purchaser, email, phone, order number, or ticket code
- Duplicate-entry warnings
- Optional re-entry with configurable limit
- Undo check-in
- Expected / checked-in / not-arrived dashboard
- Check-in event history table
- Mail-app delivery link from public ticket confirmation
- Migration milestone 019

NOTE:
Automated transactional email requires an email provider/SMTP integration. V1 provides mobile ticket links and a prefilled mail-app delivery action.
