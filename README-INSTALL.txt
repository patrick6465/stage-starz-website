STAGE STARZ ATTENDANCE CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/attendance_center.html
- templates/take_attendance.html
- templates/attendance_history.html

CONFIRM PRESENT:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/admin_login.html templates/attendance_center.html templates/take_attendance.html templates/attendance_history.html
git commit -m "Add Stage Starz Attendance Center"
git push origin railway-deployment

FEATURES:
- Attendance sessions by class and date
- Present, Late, Absent, Excused, and Unmarked statuses
- Mobile-friendly bulk attendance form
- Minutes-late tracking
- Individual attendance notes
- Lesson topic and teacher notes
- Scheduled, Completed, and Cancelled session status
- Daily attendance dashboard
- Searchable attendance history
- Attendance-rate calculations
- Teacher accounts only access assigned classes
- Owner and Office Staff access all attendance
- Migration Center milestone 011

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Migration Center shows Attendance Center.
5. Open /admin/attendance.
6. Open a class and mark the roster.
7. Save attendance, topic, and notes.
8. Open /admin/attendance/history.
9. Sign in as a Teacher and verify only assigned classes appear.
