STAGE STARZ WORKFLOW & NOTIFICATION ENGINE V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/workflow_center.html
- templates/notifications_center.html

CONFIRM PRESENT:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/admin_login.html templates/workflow_center.html templates/notifications_center.html
git commit -m "Add Stage Starz workflow and notification engine"
git push origin railway-deployment

V1 FEATURES:
- Workflow event log
- Configurable event-based rules
- Dashboard notification action
- Workflow task queue
- Completed and pending task states
- Per-user notifications
- Mark read and dismiss controls
- Manual event testing
- Automatic billing charge events
- Automatic billing payment events
- Owner, Office Staff, and Store Manager access
- Migration Center milestone 013

NOT INCLUDED YET:
- Email delivery
- SMS delivery
- Push notifications
- Background scheduler
- External message-provider credentials

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Migration Center shows Workflow and Notification Engine.
5. Open /admin/workflows.
6. Create a rule for event type billing_charge_created.
7. Add a billing charge.
8. Verify the event, task, and notification are created.
9. Open /admin/notifications.
10. Mark a notification read and dismiss it.
