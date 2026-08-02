STAGE STARZ USER NAME AND LOGOUT FIX

REPLACE:
- app.py
- templates/dashboard.html

CONFIRM PRESENT:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/admin_login.html
git commit -m "Fix user greeting and add logout controls"
git push origin railway-deployment

RESULT:
- Generic display names such as Manager fall back to the username.
- Lisa displays as Lisa.
- Visible logout controls appear in the sidebar, top-right toolbar, and mobile navigation.
