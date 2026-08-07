STAGE STARZ PARENT PORTAL V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/parent_login.html
- templates/parent_dashboard.html
- templates/parent_students.html
- templates/parent_student_profile.html
- templates/parent_schedule.html
- templates/parent_attendance.html
- templates/parent_billing.html
- templates/parent_costumes.html
- templates/parent_recitals.html
- templates/parent_tickets.html
- templates/parent_messages.html
- templates/parent_message.html
- templates/parent_documents.html
- templates/parent_profile.html
- templates/parent_portal_admin.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/parent_*.html
git commit -m "Add secure Stage Starz parent portal"
git push origin railway-deployment

PARENT PORTAL V1:
- Secure parent email/password login
- One parent account per family
- Temporary-password enforcement
- Parent logout
- Family dashboard
- Dancer profiles
- Active class schedule
- Attendance history
- Billing summary, charges, and payments
- Costume assignments and pickup status
- Recital routines and rehearsals
- Family ticket orders and mobile-ticket links
- Notification Center family inbox
- Read/unread message tracking
- Family/global document links
- Parent contact information editing
- Parent password changes
- Portal activity logging

ADMIN:
- Parent Portal Access Center
- Create family logins
- Disable/reactivate logins
- Reset temporary passwords
- Add family-specific or all-family documents
- Open Parent Login directly for testing

DATA MODEL:
The portal reads the same family, student, class, attendance, billing, costume,
recital, ticketing, and notification tables used by the admin system.
There is no duplicate family/student database.

MIGRATION CENTER:
021_parent_portal

TEST:
1. Deploy and verify /health and /ready.
2. Confirm milestone 021.
3. Open /admin/parent-portal.
4. Create a parent login for a test family with an 8+ character temporary password.
5. Open /parent/login in a private/incognito window.
6. Sign in with the family account.
7. Verify the dashboard only shows that family's dancers and data.
8. Test My Dancers, Schedule, Attendance, Billing, Costumes, Recitals, Tickets, Messages, Documents.
9. Change the parent contact information.
10. Change the temporary password.
11. Log out and log back in.
12. Disable the account in Admin and verify login is denied.
