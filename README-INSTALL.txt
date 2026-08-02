STAGE STARZ BILLING & TUITION CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html
- templates/family_profile.html

ADD:
- templates/billing_center.html
- templates/family_billing.html
- templates/billing_receipt.html

CONFIRM PRESENT:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/family_profile.html templates/admin_login.html templates/billing_center.html templates/family_billing.html templates/billing_receipt.html
git commit -m "Add Stage Starz Billing and Tuition Center"
git push origin railway-deployment

V1 FEATURES:
- Family billing accounts
- Tuition and fee charges
- Optional student-linked charges
- Cash, check, Venmo, and externally processed payment records
- Due dates and overdue totals
- Family balances and account credits
- Search and balance filters
- Printable receipts
- Payment references and notes
- Immutable audit history with charge/payment voiding
- Owner and Office Staff access
- Migration Center milestone 012

SECURITY:
- No card numbers, bank details, or payment credentials are stored.
- Credit card and ACH entries are recorded only as externally processed payments.
- Online card processing requires a later payment-provider integration.

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Migration Center shows Billing and Tuition Center.
5. Open /admin/billing.
6. Open a family account.
7. Add a test tuition charge.
8. Record a test cash payment.
9. View or print the receipt.
10. Verify the balance and ledger.
11. Void test transactions if desired.
