STAGE STARZ CLASS MANAGEMENT V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/classes.html
- templates/class_form.html
- templates/class_profile.html
- templates/teachers.html

CONFIRM PRESENT:
- templates/admin_login.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/admin_login.html templates/classes.html templates/class_form.html templates/class_profile.html templates/teachers.html
git commit -m "Add Stage Starz class management"
git push origin railway-deployment

FEATURES:
- Teachers directory
- Optional link between a Teacher record and Teacher login account
- Classes with category, level, season, room, day, time, capacity, and status
- Student enrollment and roster management
- Active, Waitlist, Dropped, and Completed enrollment statuses
- Capacity and spaces-left calculations
- Teacher accounts see only their assigned classes
- Teachers can view rosters but cannot edit classes or enrollment
- Office Staff and Owner can manage teachers, classes, and enrollment
- Migration Center milestone 010

VERIFY:
1. Railway becomes Active.
2. /health is ok.
3. /ready is ready.
4. Migration Center shows Class Management.
5. Open /admin/teachers and create a teacher.
6. Open /admin/classes and create a test class.
7. Enroll one student.
8. Link a Teacher login account and confirm it sees only assigned classes.
