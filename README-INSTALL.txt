STAGE STARZ STORE ADMIN LINK

REPLACE:
- templates/store.html

INSTALL:
git checkout railway-deployment
git add templates/store.html
git commit -m "Add Command Center links to storefront"
git push origin railway-deployment

RESULT:
- The store header includes a discreet Command Center button.
- The store footer includes a backup Admin Command Center link.
- Both links open /admin and use the existing secure login.
