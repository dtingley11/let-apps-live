# Let Apps Live — companion app

Manages ColorOS's notification retention list:

`sys_not_auto_clear_notification_config_pkg_list`

## Setup

Install the bundled KernelSU module and reboot. It installs this APK as a normal
app for Android user 0 and grants its settings permission. The app needs no
root authorization, Shizuku, or ongoing ADB connection. Check the module's
**Action** report if settings access is missing.

For a standalone installation, an ADB grant is also available where allowed:

```sh
adb shell pm grant io.github.dtingley11.letappslive android.permission.WRITE_SECURE_SETTINGS
```

Some ColorOS builds block ordinary ADB grants; the bundled module handles setup
on the tested Ace firmware. The permission normally survives reboots and app
updates. The app writes only the named setting and requests package visibility
to list installed apps. It has no network access or notification listener.

## Controls

Search apps, filter All/User/System, and change individual entries or the current
filtered results. Updated system apps remain classified as system apps.

**Automatically include user apps** updates the list on open and permitted boot
refreshes. Turning an individual user app off excludes it from that policy.
Turning the policy off leaves existing selections intact. New installs made
while the app is closed wait for a refresh; there is no polling or persistent
service. ColorOS may restrict boot refresh.

Edits preserve unrelated entries and are checked after writing. The original
value is saved privately before the first change. **More → Restore original
list** restores it and turns automatic inclusion off. Uninstalling the app does
not reset the setting.

Switches show list membership. Apps can still remove their own notifications;
changes do not restore alerts already dismissed. Auto launch and cleanup policy
are managed separately.

## Build

Requires Python 3, JDK 17+, Android SDK platform 36, and build-tools 36.0.0.
No Gradle download or third-party runtime library is required.

```sh
python3 test_policy.py
python3 build.py
```

Use `--sdk PATH` or `ANDROID_HOME` for the SDK location. APKs are written to
`dist/`. Keep the ignored `.signing/debug.keystore` to build compatible updates.
