MAIN WEBSITE IMAGE FIX

Replace only app.py in your railway-deployment branch.

This fixes the main Stage Starz website images by serving root-level assets such as:
/assets/images/audriana-homepage-hero.jpg

The store and /uploads product-image system are unchanged.

Commands:
git checkout railway-deployment
git add app.py
git commit -m "Fix main website asset paths"
git push origin railway-deployment
