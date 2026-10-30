# Changelog

## 0.4.0

- Replaced the Ace 6T firmware restriction with checks for compatible OnePlus China ROMs.
- Added cleanup rules based on each device's native and downloaded Athena policies.
- Added checks that require policy refresh after firmware or Athena changes.

## 0.3.0

- Bundled the notification manager APK with the cleanup module.
- Added automatic APK installation and settings-permission setup.
- Removed the app's root setup flow; the companion no longer needs Superuser authorization.
- Added companion permission status to the module's Action report.

## Companion 0.1.1

- Added one-time root setup for settings access.

## Companion 0.1.0

- Added per-app switches, All/User/System filters, and bulk edits.
- Added automatic user-app selection with individual exclusions.
- Added settings backup and restore.

## 0.2.0

- Extended cleanup exceptions to user apps installed for Android user 0.
- Added package-list refresh at installation and boot.
- Preserved existing native app rules and excluded system apps from automatic coverage.
- Added pending-app and live-policy checks to the Action report.

## 0.1.0

- Added the Discord-only cleanup exception.
