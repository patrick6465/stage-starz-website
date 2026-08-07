STAGE STARZ PARENT PORTAL V1.1

REPLACE:
- app.py
- templates/parent_portal_admin.html

INSTALL:
git checkout railway-deployment
git add app.py templates/parent_portal_admin.html
git commit -m "Separate parent account status from password reset"
git push origin railway-deployment

FIX:
- Enable/disable no longer shares a form with the password field.
- Account status updates NEVER read or modify password_hash.
- Account status updates NEVER modify must_change_password.
- Re-enabling an account preserves the existing password.
- Password reset now has a dedicated route and dedicated form.
- Password field uses autocomplete=new-password.
- Browser/password-manager autofill can no longer reset a password when status is changed.
- Parent Portal activity log records admin enable/disable and password-reset actions.

TEST:
1. Log in as a parent using Password A.
2. Log out.
3. Disable that parent account in /admin/parent-portal.
4. Verify Password A cannot log in while disabled.
5. Re-enable the account WITHOUT using Reset Password.
6. Verify Password A works immediately.
7. Use Reset Password and set Password B.
8. Verify Password A no longer works.
9. Verify Password B works and parent is required to change it.
