STAGE STARZ COSTUME MANAGEMENT V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/costume_center.html
- templates/costume_profile.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/admin_login.html templates/costume_center.html templates/costume_profile.html
git commit -m "Add Stage Starz costume management"
git push origin railway-deployment

VERIFY:
1. Railway Active; /health ok; /ready ready.
2. Migration Center shows milestone 015.
3. Add vendor and costume.
4. Assign costume to class.
5. Confirm students appear.
6. Update sizes/statuses and create test billing charge.
