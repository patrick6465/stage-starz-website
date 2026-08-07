STAGE STARZ STAFF PORTAL & INSTRUCTOR CENTER V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/staff_login.html
- templates/staff_dashboard.html
- templates/staff_schedule.html
- templates/staff_class.html
- templates/staff_attendance.html
- templates/staff_student.html
- templates/staff_recitals.html
- templates/staff_costumes.html
- templates/staff_competitions.html
- templates/staff_announcements.html
- templates/staff_documents.html
- templates/staff_profile.html
- templates/staff_portal_admin.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/staff_*.html
git commit -m "Add secure staff portal and instructor center"
git push origin railway-deployment

STAFF PORTAL V1:
- Separate secure instructor login at /staff/login
- Temporary password enforcement
- Mobile-friendly staff dashboard
- Only classes assigned to the logged-in teacher
- Instructor schedule
- Class rosters
- Attendance entry and editing
- Attendance session topic/teacher notes
- Student profiles limited to students the teacher actively teaches
- Instructor student notes
- Recital routines for assigned classes
- Costume assignments for assigned classes
- Competition routines for assigned classes
- Staff announcements
- Staff documents
- Instructor profile and password change
- Staff portal activity log

ADMIN:
- /admin/staff-portal
- Create instructor logins from existing teacher records
- Enable/disable accounts without changing passwords
- Separate temporary-password reset
- Post staff announcements
- Add documents for all instructors or one instructor

SECURITY:
- Staff account is linked to exactly one teacher record.
- Class pages require classes.teacher_id to match the logged-in teacher.
- Student pages require an active enrollment in one of that teacher's classes.
- Attendance can only be entered for that teacher's classes.
- Recital, costume, and competition queries are restricted by teacher-owned class_id.

MIGRATION CENTER:
022_staff_portal

TEST:
1. Deploy and verify /health and /ready.
2. Confirm milestone 022.
3. Open /admin/staff-portal.
4. Create a temporary login for one teacher.
5. Open /staff/login in an incognito/private window.
6. Log in and change the temporary password.
7. Verify only that teacher's assigned classes appear.
8. Open a class and confirm only its roster appears.
9. Take attendance for a test date and refresh to confirm it persisted.
10. Open a student and add an instructor note.
11. Verify Recitals, Costumes, and Competitions are limited to assigned classes.
12. Test announcements and documents.
13. Disable the staff account and verify login is denied.
14. Re-enable it and verify the existing password still works.
