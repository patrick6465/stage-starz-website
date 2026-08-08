STAGE STARZ INTEGRATED V2.0 — PORTAL RECOVERY & INTEGRITY MERGE

BASE:
- Latest Recital Production Center V1 build

RESTORED FROM SAVED PORTAL SNAPSHOTS:
- Parent Portal
- Staff / Teacher Portal
- Digital Ticket Delivery & Door Check-In
- Notification Center

PRESERVED FROM CURRENT BUILD:
- Recital Production Center
- Public Reserved Ticket Sales
- Coordinate Venue Designer / mouse positioning
- Reserved Ticketing / holds
- Competition Center
- Costume Center
- Billing & Tuition
- Attendance
- Student / Family / Customer CRM
- Workflow, Users/Roles, Migration Center, Developer Center

REPLACE:
- app.py
- database.py
- requirements.txt
- templates/dashboard.html
- templates/ticket_show.html
- templates/ticket_order.html
- templates/public_ticket_order.html

ADD ALL NEW PORTAL / NOTIFICATION / CHECK-IN TEMPLATES FROM THIS PACKAGE.
The safest installation method is to copy the complete contents of this ZIP over the current project, preserving newer files.

DEPLOY:
git checkout railway-deployment
git add .
git commit -m "Restore parent staff portals and integration baseline"
git push origin railway-deployment

MIGRATION MILESTONES AFTER MERGE:
019_recital_production_center
020_digital_ticket_delivery_checkin
021_email_notification_center
022_parent_portal
023_staff_portal

VERIFY:
1. /health
2. /ready
3. /admin/production
4. /admin/parent-portal
5. /parent/login
6. /admin/staff-portal
7. /staff/login
8. /admin/notifications
9. Ticket show check-in center and mobile ticket links
10. Migration Center milestones 019 through 023
