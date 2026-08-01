STAGE STARZ HOMEPAGE EDITOR V1

REPLACE:
- app.py
- templates/dashboard.html

ADD:
- templates/homepage_editor.html

INSTALL:
git checkout railway-deployment
git add app.py templates/dashboard.html templates/homepage_editor.html
git commit -m "Add homepage editor"
git push origin railway-deployment

OPEN:
- /admin/website/homepage

CONTROLS:
- Announcement bar on/off and text
- Hero kicker, headline and supporting text
- Hero background image upload or media selection
- Primary and secondary button text/links
- Optional countdown label and date
- Live homepage preview

The editor does not rewrite site/index.html. It safely injects the saved settings
at runtime, preserving the current design and main-site image paths.
