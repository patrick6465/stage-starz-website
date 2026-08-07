STAGE STARZ REPORTING & BUSINESS INTELLIGENCE CENTER V1.1

REPLACE:
- app.py

INSTALL:
git checkout railway-deployment
git add app.py
git commit -m "Fix reporting CSV downloads"
git push origin railway-deployment

FIX:
- CSV exports no longer call the missing Flask make_response function.
- CSV responses now use the already imported Flask Response class.
- UTF-8 BOM added for better Microsoft Excel compatibility.
- Standard CRLF CSV line endings used.
- Cache-Control no-store added to downloads.

RETEST THESE FOUR DOWNLOADS:
1. /admin/reports/export/families.csv
2. /admin/reports/export/enrollment.csv
3. /admin/reports/export/attendance.csv
4. /admin/reports/export/tickets.csv

EXPECTED:
- Browser downloads a .csv file.
- File opens normally in Excel.
- Column headings are present.
- Report records match the live Reporting Center data.
