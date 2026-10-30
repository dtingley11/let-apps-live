#!/system/bin/sh

LAL_PACKAGE=io.github.dtingley11.letappslive
LAL_VERSION_CODE=4

lal_package_path() {
    timeout 10 /system/bin/pm path --user 0 "$LAL_PACKAGE"
}

lal_package_dump() {
    timeout 10 /system/bin/dumpsys package "$LAL_PACKAGE"
}

lal_install_apk() {
    # Stream the APK; PackageManager need not read /data/adb directly.
    timeout 60 /system/bin/pm install -r --user 0 -S "$1" < "$LAL_APK"
}

lal_grant_permission() {
    timeout 10 /system/bin/pm grant --user 0 "$LAL_PACKAGE" android.permission.WRITE_SECURE_SETTINGS
}

lal_has_permission() {
    printf '%s\n' "$1" | grep -Eq '^[[:space:]]*android\.permission\.WRITE_SECURE_SETTINGS: granted=true([[:space:],]|$)'
}

lal_installed_hash() {
    lal_paths=$(lal_package_path) || return 1
    lal_path=$(printf '%s\n' "$lal_paths" | sed -n 's/^package://p')
    [ -n "$lal_path" ] && [ -f "$lal_path" ] || return 1
    lal_hash=$(sha256sum "$lal_path") || return 1
    printf '%s\n' "${lal_hash%% *}"
}

lal_fail() {
    printf '%s\n' "$1" > "$MODDIR/companion-status.txt"
    return 1
}

lal_companion_sync() {
    if [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/skip_mount" ] ||
       [ -f "$MODDIR/skip_mountify" ] || ! athena_check install; then
        lal_fail 'Companion setup skipped: module compatibility/integrity check failed.'
        return 1
    fi
    LAL_APK="$MODDIR/companion/LetAppsLive.apk"
    lal_expected=$(awk '$2 == "companion/LetAppsLive.apk" { print $1 }' "$MODDIR/resources.sha256")
    if ! printf '%s\n' "$lal_expected" | grep -Eq '^[0-9a-f]{64}$'; then
        lal_fail 'Companion setup refused: no valid bundled APK digest.'
        return 1
    fi
    lal_installed=$(lal_installed_hash) || lal_installed=
    lal_installed_now=no
    if [ "$lal_installed" != "$lal_expected" ]; then
        lal_dump=$(lal_package_dump) || {
            lal_fail 'Companion setup deferred: PackageManager is not available.'
            return 1
        }
        lal_code=$(printf '%s\n' "$lal_dump" | sed -n 's/^[[:space:]]*versionCode=\([0-9][0-9]*\).*$/\1/p' | head -n 1)
        if [ -n "$lal_code" ] && [ "$lal_code" -gt "$LAL_VERSION_CODE" ]; then
            if lal_has_permission "$lal_dump"; then
                printf '%s\n' 'Ready: newer companion retained; existing settings permission verified. No install or grant performed.' > "$MODDIR/companion-status.txt"
                return 0
            fi
            lal_fail 'Companion setup refused: newer app lacks permission; update the module bundle to verify that APK.'
            return 1
        fi
        lal_size=$(wc -c < "$LAL_APK") || return 1
        if ! lal_install_apk "$lal_size" > "$MODDIR/companion-install.log" 2>&1; then
            lal_fail 'Companion installation failed; existing app/data retained. See companion-install.log.'
            return 1
        fi
        lal_installed_now=yes
        lal_installed=$(lal_installed_hash) || lal_installed=
        if [ "$lal_installed" != "$lal_expected" ]; then
            lal_fail 'Companion permission not granted: installed APK does not match the verified bundle.'
            return 1
        fi
    fi
    lal_dump=$(lal_package_dump) || {
        lal_fail 'Companion permission check failed: PackageManager is not available.'
        return 1
    }
    if lal_has_permission "$lal_dump"; then
        printf 'Ready: companion verified (installed now: %s); settings permission already granted.\n' "$lal_installed_now" > "$MODDIR/companion-status.txt"
        return 0
    fi
    if ! lal_grant_permission > "$MODDIR/companion-grant.log" 2>&1; then
        lal_fail 'Companion permission grant failed. See companion-grant.log; setup will retry at the next normal boot.'
        return 1
    fi
    lal_dump=$(lal_package_dump) || return 1
    if ! lal_has_permission "$lal_dump"; then
        lal_fail 'Companion permission grant could not be verified.'
        return 1
    fi
    printf 'Ready: companion verified (installed now: %s); settings permission granted and verified.\n' "$lal_installed_now" > "$MODDIR/companion-status.txt"
}

lal_companion_report() {
    lal_paths=$(lal_package_path) || lal_paths=
    if [ -z "$lal_paths" ]; then
        printf '%s\n' 'Companion app: not installed.'
        return 1
    fi
    printf '%s\n' 'Companion app: installed.'
    lal_dump=$(lal_package_dump) || return 1
    if lal_has_permission "$lal_dump"; then
        printf '%s\n' 'Settings permission: granted.'
    else
        printf '%s\n' 'Settings permission: missing. Reboot to run module setup.'
        return 1
    fi
}
