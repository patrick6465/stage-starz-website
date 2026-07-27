STAGE STARZ COLOR TOGGLE UPDATE

Replace these files in your local stage-starz-website project:

1. app.py
2. templates/admin.html
3. templates/store.html

Then commit and push:

git checkout railway-deployment
git add app.py templates/admin.html templates/store.html
git commit -m "Add optional product color selection"
git push origin railway-deployment

What this update does:
- Adds an Offer color selection checkbox in the admin.
- Existing products default to showing colors.
- Unchecking the option removes Color from the product page.
- Color is also omitted from the cart and order email.
- Existing Railway database/product data is preserved by an automatic migration.
