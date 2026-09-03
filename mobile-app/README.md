# Stage Starz Mobile — Version 1.1

A simple Expo/React Native mobile hub for Stage Starz Academy of Dance.

## Included in Version 1

### Families
- Jackrabbit Parent Portal
- Payments and family account access through Jackrabbit
- Class schedules through Jackrabbit
- Class Finder
- Recital information
- Competition information
- Parent Hub
- Stage Starz Shop

### Teachers & Staff
- Jackrabbit Teacher & Staff Portal
- Classes
- Rosters
- Attendance
- Time clock
- Stage Starz Management Center
- Website Traffic

### Everyone
- Studio phone
- Email
- Directions
- Website
- Google review link

## Security

Version 1 does not store Jackrabbit or Stage Starz management passwords in the app.
Protected features open the existing secure login pages.

## Test with Expo

This project uses Expo SDK 54 for easy Expo Go testing.

1. Install Node.js 20.19 or newer.
2. Open a terminal in the mobile-app folder.
3. Run:

   npm install

4. Then run:

   npx expo start

5. Scan the QR code using Expo Go.

## Android APK later

After testing, configure EAS and run:

   npx eas build --platform android --profile preview

The included eas.json is configured for an internal APK build.

## Important URLs

Portal URLs are kept in:

src/links.js

That makes it easy to update Jackrabbit or Stage Starz links without redesigning the app.

## Version 1.1

- Fixed Android status-bar overlap at the top.
- Raised the bottom navigation above Android system buttons.
- Kept Expo SDK 57 compatibility.
