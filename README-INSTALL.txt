STAGE STARZ REPORTING & BUSINESS INTELLIGENCE CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/reporting_center.html
- templates/report_financial.html
- templates/report_enrollment.html
- templates/report_attendance_bi.html
- templates/report_operations.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/report*.html
git commit -m "Add reporting and business intelligence center"
git push origin railway-deployment

MILESTONE:
023_reporting_business_intelligence

V1 FEATURES:
- Executive KPI dashboard
- Active families, students, classes, enrollments
- Total charges, posted payments, open balances
- Attendance present-rate KPI
- Valid tickets, ticket revenue, checked-in counts
- Monthly payment revenue
- Class utilization / fill percentages
- Instructor workload
- Financial family balance report
- Payments by method
- Enrollment and fill report
- Student status report
- Attendance by class
- Students with most absences/lates
- Recital operations report
- Costume pipeline financial summary
- Competition routines/dancers/awards summary
- Ticketing sales/check-in summary
- CSV exports for family balances, enrollment, attendance, and ticket sales
- Executive snapshot history

VERIFY:
1. Railway Active.
2. /health and /ready pass.
3. Migration Center shows milestone 023.
4. Open /admin/reports.
5. Verify KPI numbers against known records.
6. Open Financial, Enrollment, Attendance, and Operations.
7. Download all four CSV exports.
8. Save an Executive Snapshot and confirm it appears in snapshot history.
