STAGE STARZ CRM CUSTOMER SCHEMA FIX

ERRORS FIXED:
- column "order_count" of relation "customers" does not exist
- column "last_order_at" does not exist

CAUSE:
An older customers table already existed. CREATE TABLE IF NOT EXISTS does not
add new columns to an existing PostgreSQL table.

REPLACE:
- database.py

INSTALL:
git checkout railway-deployment
git add database.py
git commit -m "Upgrade existing customer CRM schema"
git push origin railway-deployment

WHAT THIS DOES:
- Adds missing CRM columns with ALTER TABLE ... ADD COLUMN IF NOT EXISTS
- Preserves existing customer records
- Adds order_count
- Adds lifetime_value
- Adds last_order_at
- Adds phone, status, tags, notes, created_at, and updated_at when missing
- Keeps SQLite local fallback compatible

AFTER DEPLOYMENT:
1. Confirm Railway is Active.
2. Open /health.
3. Open /ready.
4. Open /admin/customers.
5. Existing orders should backfill into customer records.
