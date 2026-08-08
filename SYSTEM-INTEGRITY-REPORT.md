# Stage Starz V2.0 System Integrity Report

This package uses the Recital Production Center release as the current baseline and merges the later portal branch back into it.

## Verified present in source

- Customer CRM
- Family Foundation
- Student Management
- Class Management
- Attendance Center
- Billing & Tuition Center
- Workflow Center
- Recital Management
- Costume Management
- Competition Management
- Reserved Ticketing
- Coordinate Venue Designer and mouse drag positioning
- Public Reserved Ticket Sales
- Recital Production Center / Live Stage Manager
- Digital Ticket Delivery and Door Check-In
- Notification Center
- Parent Portal
- Staff / Teacher Portal
- User and Role Management
- Migration Center
- Developer Center

## Portal routes restored

Parent portal: `/parent/login`, `/parent`, students, schedule, attendance, billing, costumes, recitals, tickets, messages, documents, profile, and `/admin/parent-portal`.

Staff portal: `/staff/login`, `/staff`, schedule, assigned classes, attendance, students, recitals, costumes, competitions, announcements, documents, profile, and `/admin/staff-portal`.

## Regression protection

The Command Center no longer contains the old `Parent Portal — Later` placeholder. It now contains administration and direct-open links for both Parent and Staff portals. The newer Production Center remains present.
