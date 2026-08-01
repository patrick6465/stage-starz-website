STAGE STARZ HOMEPAGE EDITOR + ADMIN LINK FIX

REPLACE:
- app.py
- templates/dashboard.html

KEEP/VERIFY:
- templates/homepage_editor.html must already exist from the Homepage Editor update.

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html
git commit -m "Fix homepage editor link and add admin shortcut"
git push origin railway-deployment

AFTER RAILWAY REDEPLOYS:
- Open /admin
- Homepage Editor should be an active link, with no "Next" label.
- The main homepage will show a discreet Admin button in the lower-right corner.
- The Admin button opens /admin and uses the existing secure login.
