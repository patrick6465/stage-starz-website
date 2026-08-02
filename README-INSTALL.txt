STAGE STARZ LOGIN TEMPLATE FIX

CAUSE:
The roles upgrade changed /admin/login to render templates/admin_login.html,
but that file was not included. Flask returned a 500 error when opening login.

ADD:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add templates/admin_login.html
git commit -m "Add missing administrator login template"
git push origin railway-deployment

AFTER DEPLOYMENT:
1. Open /admin/login.
2. Sign in using the original administrator username and password.
3. The login process will create or refresh the Owner account.
4. Open /admin/system/users.
