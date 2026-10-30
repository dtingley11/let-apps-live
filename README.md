# Let Apps Live

A KernelSU module and Android companion for ColorOS notification behavior.
The module changes user-app cleanup from force-stop to ordinary process kill.
The companion manages which apps retain posted notifications during cleanup.

## Tested setup

- OnePlus Ace 6T (PLR110), ColorOS 16 / Android 16.
- Firmware: `PLR110_16.0.10.500(CN01)`.
- KernelSU Next with Mountify in automatic mode.

The current installer checks for this exact firmware and its original
configuration. Compatibility with other setups has not been verified.

If installation is rejected or something isn't working,
[open an issue](https://github.com/dtingley11/let-apps-live/issues/new).
Include your device, firmware, root manager, and installer or Action output.

## Install

1. Download the ZIP from [Releases](https://github.com/dtingley11/let-apps-live/releases/latest)
   and install it in KernelSU Manager.
2. Reboot to activate the cleanup configuration.
3. Open **Let Apps Live** and select the apps whose notifications should remain.
4. Use the module's **Action** report to check cleanup coverage and app access.

The ZIP includes the APK. Module setup installs it as a normal app for Android
user 0 and grants `WRITE_SECURE_SETTINGS`. If setup cannot finish during
installation, a one-shot boot task retries after Android starts, then exits.
The companion needs no root authorization or Shizuku.

Updates preserve the installed app's data and notification selections. The
module retains its original ID, `discord_athena_usekill`, for in-place upgrades.
Removing the module does not uninstall the companion or reset its selections.

Open previously force-stopped apps once to make them eligible for pushes again.
ColorOS's **Auto launch** permission is separate and may also need enabling.
The bundle does not change Auto launch or battery optimization.

## App controls

- Filter **All apps**, **User apps**, or **System**, and search by name or package.
- Change individual apps or enable/disable the current filtered results.
- Enable **Automatically include user apps** to update the retention list on
  open and permitted boot refreshes. Individual exclusions remain respected.
- Use **More → Restore original list** to restore the value saved before the
  companion's first change.

System apps, including updated system apps, are excluded from the automatic
user-app selection. Apps can still dismiss their own notifications.

New user apps receive cleanup exceptions on the next reboot. Automatic
notification retention waits for an app refresh; there is no background
polling or persistent install watcher.

## Build

Requires Python 3, JDK 17+, Android SDK platform 36, build-tools 36.0.0, `awk`,
and `sh`. Set `ANDROID_HOME` if the SDK is not under `~/Android/Sdk`.

```sh
python3 build.py
python3 -m unittest -v
python3 manager/test_policy.py
```

The build produces the companion APK and bundled module ZIP under their
respective `dist/` directories. Keep `manager/.signing/` to sign compatible app
updates; keys and build outputs are excluded from Git.

The build uses `inputs/seed-apps.txt`; installation and boot replace that seed
with the device's user-app inventory. Use `--packages PATH` for a custom sorted
seed manifest.

See [manager/](manager/) for companion details and [CHANGELOG.md](CHANGELOG.md)
for changes. Earlier source snapshots remain under [history/](history/).
