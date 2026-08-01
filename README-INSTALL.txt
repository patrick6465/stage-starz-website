STAGE STARZ ANNOUNCEMENT MANAGER V1

REPLACE:
- app.py
- templates/dashboard.html

ADD:
- templates/announcements.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/announcements.html
git commit -m "Add announcement manager"
git push origin railway-deployment

OPEN:
- /admin/announcements

The highest-priority active announcement within its start/end dates appears automatically on the homepage.
