STAGE STARZ PERSONALIZED DASHBOARD GREETING FIX

CAUSE:
The Command Center greeting was hard-coded as "Patrick" in dashboard.html.

REPLACE:
- templates/dashboard.html

INSTALL:
git checkout railway-deployment
git add templates/dashboard.html
git commit -m "Personalize Command Center greeting"
git push origin railway-deployment

RESULT:
- Patrick sees his own display name.
- Lisa sees Lisa.
- Every administrator sees the display name stored on their account.
- Roles and permissions remain unchanged.
