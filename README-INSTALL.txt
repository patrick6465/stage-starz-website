STAGE STARZ USERS, ROLES & PERMISSIONS V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/admin_users.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/admin_users.html
git commit -m "Add Stage Starz users roles and permissions"
git push origin railway-deployment

The current ADMIN_USERNAME and ADMIN_PASSWORD remain the Owner recovery login.

VERIFY:
1. Railway Active
2. /health ok
3. /ready ready
4. Sign in with current admin credentials
5. Open /admin/system/users
6. Create and test an Office Staff account
