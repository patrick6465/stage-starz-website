STAGE STARZ WEBSITE + STARDUST STORE ADMIN
==========================================

This package combines:

1. The Stage Starz public website
2. The Stardust Ship-it-Shop storefront
3. A private store administration dashboard
4. A SQLite product and settings database

WEB ADDRESSES
-------------

Main website:
http://127.0.0.1:5000/

Store:
http://127.0.0.1:5000/store

Admin dashboard:
http://127.0.0.1:5000/admin

Temporary admin login:
Username: admin
Password: StageStarz123!

Change the login before publishing online.

WHAT THE ADMIN CONTROLS
-----------------------

- Products
- Prices and sale prices
- Categories
- Inventory
- Sizes and colors
- Product-specific fulfillment fees
- Add-a-Name availability by product
- The global name charge
- Product visibility
- Product image URLs
- Sales-tax rate
- Order email
- Venmo username

ADDING THE REST OF YOUR WEBSITE
-------------------------------

The recovered homepage is included at:

site/index.html

Place all other existing website HTML pages, images, CSS, and assets inside
the "site" folder while preserving their current file names and subfolders.

The application's existing Shop links have been changed to:

/store

RUNNING LOCALLY ON WINDOWS
--------------------------

1. Install Python 3.
2. Extract this ZIP.
3. Open Command Prompt in the extracted folder.
4. Run:

py -m pip install -r requirements.txt
py app.py

ONLINE HOSTING
--------------

This application needs Python hosting because the admin dashboard and database
cannot run as a plain Wix HTML embed.

Suitable hosting choices include PythonAnywhere, Render, Railway, or a VPS.

For the cleanest setup, use a subdomain such as:

shop.stagestarzdance.net

Alternatively, move the whole custom website to the Python host and point the
main stagestarzdance.net domain to it.

SECURITY
--------

Set these environment variables before publishing:

ADMIN_USERNAME
ADMIN_PASSWORD
SECRET_KEY

Do not publish using the temporary password.
