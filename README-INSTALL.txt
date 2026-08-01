STAGE STARZ STUDENT FOUNDATION V1

REPLACE:
- app.py
- database.py
- templates/dashboard.html

ADD:
- templates/students.html
- templates/student_form.html
- templates/student_profile.html

INSTALL:
git checkout railway-deployment
git add app.py database.py templates/dashboard.html templates/students.html templates/student_form.html templates/student_profile.html
git commit -m "Add Stage Starz Student Foundation"
git push origin railway-deployment

FEATURES:
- PostgreSQL students table
- PostgreSQL student_notes table
- Family linking
- Student list, search, filters, and sorting
- Add and edit student profiles
- Student photo uploads
- Birthday tracking
- Active, Trial, Inactive, and Alumni statuses
- Competition-team designation
- School and grade
- Leotard, costume, shoe, and warmup sizes
- Medical and general notes
- Student tags
- Dated student timeline notes
- Student deletion
- Migration Center milestone 008
- Command Center Students navigation

SAFETY:
- Schema-only startup migration
- No student backfill during Railway deployment
- Existing family, customer, order, and store data remains unchanged
- /health and /ready behavior remains unchanged

VERIFY:
1. Railway deployment becomes Active.
2. /health returns ok.
3. /ready returns ready.
4. Migration Center shows Student Foundation as Applied or Verified.
5. Open /admin/students.
6. Add one test student and link the student to a family.
7. Upload a photo and confirm the student profile loads.
