STAGE STARZ EMAIL & NOTIFICATION CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/notification_center.html
- templates/notification_template.html
- templates/notification_campaign.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/notification_center.html templates/notification_template.html templates/notification_campaign.html
git commit -m "Add email and notification center"
git push origin railway-deployment

V1 FEATURES:
- Central Notification Center
- Reusable message templates
- Categories: General, Billing, Attendance, Recital, Competition, Costume, Ticketing, Registration
- Campaign creation
- Scheduled-for date/time field
- Manual recipients
- Automatic recipient groups:
  * All Families
  * Active Students
  * Open Billing
  * Ticket Purchasers
  * Competition Families
  * Recital Families
- Internal email delivery queue
- Recipient status tracking
- Delivery history
- Mark Sent / Mark Failed test controls
- Failure reason tracking
- Workflow event when a campaign is queued
- Owner/Office notification permissions
- Migration Center milestone 020_email_notification_center

IMPORTANT:
V1 does not send email through an outside provider yet.
It builds and tests the entire communications engine safely.
The next delivery-provider upgrade can connect SMTP, Resend, SendGrid, Mailgun, or another provider without redesigning the database.

VERIFY:
1. Railway Active.
2. /health ok.
3. /ready ready.
4. Migration Center shows milestone 020.
5. Open /admin/notifications.
6. Create a template.
7. Create a campaign using All Families.
8. Confirm recipients populate.
9. Queue the campaign.
10. Confirm delivery records appear.
11. Mark one Sent and one Failed.
12. Confirm statuses and counts update.
