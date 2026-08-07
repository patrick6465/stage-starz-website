STAGE STARZ ONLINE REGISTRATION & WAITLIST SYSTEM V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html
- parent portal templates matching templates/parent_*.html

ADD:
- templates/registration_catalog.html
- templates/registration_class.html
- templates/registration_confirmation.html
- templates/parent_registration.html
- templates/registration_admin.html
- templates/registration_class_settings.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/parent_*.html templates/registration_*.html
git commit -m "Add online registration and waitlist system"
git push origin railway-deployment

MILESTONE:
024_online_registration_waitlists

V1 FEATURES:
- Public class registration catalog at /register
- Per-class publish controls
- Registration open/close dates
- Approval-required option
- Capacity enforcement
- Automatic waitlisting when a class is full
- Sequential waitlist positions
- Waitlist rebalancing after changes
- Admin Fill Openings promotion engine
- Public/new-family registration
- Returning-family registration through Parent Portal
- Existing dancer selector in Parent Portal
- Digital registration agreement / waiver acceptance
- Guardian/student/emergency/medical intake
- Registration and costume fee configuration
- Automatic Billing Center charge after enrollment
- New family/student creation only after enrollment approval/finalization
- Duplicate enrollment protection for Parent Portal
- Workflow event on public registration submission
- Admin Registration Center
- Approve / Decline applications
- Registration status and waitlist position confirmation
- Reporting data remains based on the same live enrollments

IMPORTANT:
V1 does not process credit cards. Fees become Billing Center charges.
Payment Gateway / AutoPay is the next payment milestone.

TEST:
1. Deploy; verify /health and /ready.
2. Confirm Migration Center milestone 024.
3. Open /admin/registration.
4. Configure one class with capacity 2, public registration on, waitlist on.
5. Set agreement text and registration/costume fees.
6. Open /register in incognito.
7. Submit one public registration and verify enrollment or Pending depending on approval setting.
8. Use Parent Portal Registration for an existing dancer.
9. Fill the class, then submit another registration and verify Waitlisted #1.
10. Increase capacity or create an opening, click Fill Openings, and verify #1 is enrolled.
11. Verify registration fees appear in Billing Center.
12. Verify new public families/students are created only when enrollment is finalized.
13. Verify a parent cannot enroll a dancer belonging to another family.
