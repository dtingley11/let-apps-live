#!/system/bin/sh

ATHENA_MODULE=/data/adb/modules/discord_athena_usekill

athena_error() { ATHENA_ERROR=$1; return 1; }

athena_mount_check() {
    [ -f /data/adb/modules/mountify/metamount.sh ] &&
    [ ! -f /data/adb/modules/mountify/disable ] &&
    [ ! -f /data/adb/modules/mountify/remove ] &&
    grep -Eq '^[[:space:]]*mountify_mounts=2([[:space:]]*(#.*)?)?$' /data/adb/mountify/config.sh
}

athena_check_platform() {
    ATHENA_ERROR=
    athena_brand=$(getprop ro.product.brand | tr '[:upper:]' '[:lower:]')
    athena_maker=$(getprop ro.product.manufacturer | tr '[:upper:]' '[:lower:]')
    if [ "$athena_brand" != oneplus ] && [ "$athena_maker" != oneplus ]; then
        athena_error 'This module targets OnePlus China ROMs.'; return 1
    fi
    athena_area=$(getprop ro.oplus.image.system_ext.area | tr '[:upper:]' '[:lower:]')
    athena_region=$(getprop persist.sys.oplus.region | tr '[:upper:]' '[:lower:]')
    athena_regionmark=$(getprop ro.oplus.regionmark | tr '[:upper:]' '[:lower:]')
    case "$athena_area:$athena_region:$athena_regionmark" in
        domestic:*|cn:*|*:cn:*|*:*:cn) ;;
        *) athena_error 'No OnePlus China-ROM region marker was found.'; return 1 ;;
    esac
    athena_sdk=$(getprop ro.build.version.sdk)
    case "$athena_sdk" in ''|*[!0-9]*) athena_error 'Cannot read the Android API level.'; return 1 ;; esac
    [ "$athena_sdk" -ge 30 ] || { athena_error 'Android 11 or newer is required.'; return 1; }
    athena_mount_check || { athena_error 'Enable Mountify in automatic mode.'; return 1; }
    if ! (cd "$MODDIR" && sha256sum -c resources.sha256 >/dev/null 2>&1); then
        athena_error 'Module resources failed their checksum check.'; return 1
    fi
}

athena_build_identity() {
    athena_identity=$(getprop ro.build.display.id)
    [ -n "$athena_identity" ] || athena_identity=$(getprop ro.build.fingerprint)
    [ -n "$athena_identity" ] || return 1
    printf '%s\n' "$athena_identity"
}

athena_load_target() {
    ATHENA_TARGET=$(cat "$MODDIR/device/target.txt") || return 1
    case "$ATHENA_TARGET" in
        /my_product/etc/extension/sys_custom_clear_appfilter_list.xml|/product/etc/extension/sys_custom_clear_appfilter_list.xml|/system_ext/etc/extension/sys_custom_clear_appfilter_list.xml)
            ATHENA_RELATIVE="system$ATHENA_TARGET" ;;
        /system/etc/extension/sys_custom_clear_appfilter_list.xml)
            ATHENA_RELATIVE=${ATHENA_TARGET#/} ;;
        *) athena_error 'Unsupported Athena configuration path.'; return 1 ;;
    esac
}

athena_previous_original() {
    # Recover the original only when the visible file is our verified old overlay.
    athena_previous=$ATHENA_MODULE
    athena_rel=$1
    athena_visible_hash=$2
    [ -f "$athena_previous/$athena_rel" ] || return 1
    athena_previous_hash=$(sha256sum "$athena_previous/$athena_rel") || return 1
    [ "${athena_previous_hash%% *}" = "$athena_visible_hash" ] || return 1
    if [ -f "$athena_previous/resources.sha256" ] && [ -f "$athena_previous/state.sha256" ]; then
        (cd "$athena_previous" && sha256sum -c resources.sha256 >/dev/null 2>&1 && sha256sum -c state.sha256 >/dev/null 2>&1) || return 2
        if [ -f "$athena_previous/device-state.sha256" ]; then
            (cd "$athena_previous" && sha256sum -c device-state.sha256 >/dev/null 2>&1) || return 2
            athena_previous_build=$(cat "$athena_previous/device/build-id.txt") || return 2
            [ "$athena_previous_build" = "$(athena_build_identity)" ] || return 2
            printf '%s\n' "$athena_previous/device/original-custom.xml"
        else
            # Legacy bundles stored the tested build in their checked script.
            athena_previous_build=$(sed -n "s/^ATHENA_BUILD='\([^']*\)'$/\1/p" "$athena_previous/common.sh")
            [ -n "$athena_previous_build" ] && [ "$athena_previous_build" = "$(athena_build_identity)" ] || return 2
            [ -f "$athena_previous/stock/sys_custom_clear_appfilter_list.xml" ] || return 2
            printf '%s\n' "$athena_previous/stock/sys_custom_clear_appfilter_list.xml"
        fi
    else
        return 2
    fi
}

athena_check() {
    athena_check_platform || return 1
    if ! (cd "$MODDIR" && sha256sum -c device-state.sha256 >/dev/null 2>&1 && sha256sum -c state.sha256 >/dev/null 2>&1); then
        athena_error 'Prepared device policy failed its checksum check. Reinstall the module.'; return 1
    fi
    athena_load_target || return 1
    athena_identity=$(athena_build_identity) || return 1
    if [ "$athena_identity" != "$(cat "$MODDIR/device/build-id.txt")" ]; then
        athena_error 'Firmware changed. Reinstall the module to refresh its policy.'; return 1
    fi
    athena_apk=$(cat "$MODDIR/device/athena-apk.txt") || return 1
    athena_hash=$(sha256sum "$athena_apk") || { athena_error 'Athena APK is unavailable. Reinstall the module.'; return 1; }
    if [ "${athena_hash%% *}" != "$(cat "$MODDIR/device/athena-apk.sha256")" ]; then
        athena_error 'Athena changed. Reinstall the module to refresh its policy.'; return 1
    fi
    athena_hash=$(sha256sum "$ATHENA_TARGET") || { athena_error 'Cannot read the native custom policy.'; return 1; }
    athena_hash=${athena_hash%% *}
    athena_original_hash=$(sha256sum "$MODDIR/device/original-custom.xml") || return 1
    if [ "$athena_hash" != "${athena_original_hash%% *}" ]; then
        if [ "${1:-boot}" = boot ]; then
            athena_error 'Native custom policy changed. Reinstall the module.'; return 1
        fi
        athena_generated=$(sha256sum "$MODDIR/$ATHENA_RELATIVE") || return 1
        if [ "$athena_hash" != "${athena_generated%% *}" ]; then
            athena_old_original=$(athena_previous_original "$ATHENA_RELATIVE" "$athena_hash") || {
                athena_error 'Another custom policy is active. Disable it and reboot before installing.'; return 1
            }
            athena_old_hash=$(sha256sum "$athena_old_original") || return 1
            [ "${athena_old_hash%% *}" = "${athena_original_hash%% *}" ] || {
                athena_error 'The active overlay has a different original policy.'; return 1
            }
        fi
    fi
}

athena_find_target() {
    ATHENA_TARGET=
    athena_first_hash=
    for athena_candidate in /my_product/etc/extension/sys_custom_clear_appfilter_list.xml /product/etc/extension/sys_custom_clear_appfilter_list.xml /system_ext/etc/extension/sys_custom_clear_appfilter_list.xml /system/etc/extension/sys_custom_clear_appfilter_list.xml; do
        [ -f "$athena_candidate" ] || continue
        athena_hash=$(sha256sum "$athena_candidate") || return 1
        athena_hash=${athena_hash%% *}
        if [ -n "$athena_first_hash" ] && [ "$athena_hash" != "$athena_first_hash" ]; then
            athena_error 'Multiple different Athena custom policies were found. Open an issue with the installer output.'; return 1
        fi
        if [ -z "$ATHENA_TARGET" ]; then ATHENA_TARGET=$athena_candidate; athena_first_hash=$athena_hash; fi
    done
    [ -n "$ATHENA_TARGET" ] || { athena_error 'No native Athena custom policy was found.'; return 1; }
    case "$ATHENA_TARGET" in /system/*) ATHENA_RELATIVE=${ATHENA_TARGET#/} ;; *) ATHENA_RELATIVE="system$ATHENA_TARGET" ;; esac
}

athena_find_apk() {
    for athena_package in com.oplus.athena com.coloros.athena; do
        athena_path=$(timeout 10 /system/bin/pm path --user 0 "$athena_package" 2>/dev/null | sed -n 's/^package://p' | head -n 1)
        if [ -f "$athena_path" ]; then printf '%s\n' "$athena_path"; return 0; fi
    done
    for athena_path in /system_ext/app/Athena/Athena.apk /system/app/Athena/Athena.apk /product/app/Athena/Athena.apk; do
        if [ -f "$athena_path" ]; then printf '%s\n' "$athena_path"; return 0; fi
    done
    return 1
}

athena_query_updates() {
    for athena_authority in com.oplus.romupdate.provider.db com.nearme.romupdate.provider.db; do
        if timeout 10 /system/bin/content query --uri "content://$athena_authority/update_list" --projection xml --where 'filtername="sys_clear_appfilter_list"' > "$1/remote-base.txt" 2> "$1/query-error.txt" &&
           timeout 10 /system/bin/content query --uri "content://$athena_authority/update_list" --projection xml --where 'filtername="sys_custom_clear_appfilter_list"' > "$1/remote-custom.txt" 2>> "$1/query-error.txt" &&
           grep -Eq '^[[:space:]]*(Row: 0 xml=|No result found\.?[[:space:]]*$|<)' "$1/remote-base.txt" &&
           grep -Eq '^[[:space:]]*(Row: 0 xml=|No result found\.?[[:space:]]*$|<)' "$1/remote-custom.txt"; then
            return 0
        fi
    done
    athena_error 'Cannot read downloaded Athena policies. Open an issue with the installer output.'
    return 1
}

athena_prepare_device() {
    athena_check_platform || return 1
    athena_find_target || return 1
    cp "$ATHENA_TARGET" "$1/visible.xml" || return 1
    athena_hash=$(sha256sum "$ATHENA_TARGET") || return 1
    athena_source=$(athena_previous_original "$ATHENA_RELATIVE" "${athena_hash%% *}")
    athena_source_result=$?
    if [ "$athena_source_result" = 2 ]; then
        athena_error 'Cannot reuse the previous original policy. Disable the module and reboot before reinstalling.'; return 1
    fi
    [ "$athena_source_result" = 0 ] || athena_source=$ATHENA_TARGET
    cp "$athena_source" "$1/original.xml" || return 1
    athena_apk=$(athena_find_apk) || { athena_error 'Athena APK was not found.'; return 1; }
    if ! /data/adb/ksu/bin/busybox unzip -p "$athena_apk" assets/sys_clear_appfilter_list.xml > "$1/base.xml"; then
        athena_error 'Athena does not contain the expected cleanup policy.'; return 1
    fi
    if ! timeout 10 /system/bin/dumpsys athenaservice prockill filter_list sys_use_kill > "$1/native-map.txt" || ! grep -q '\[USE KILL\]' "$1/native-map.txt"; then
        athena_error 'Athena does not expose a readable USE KILL policy.'; return 1
    fi
    athena_query_updates "$1" || return 1
    if ! timeout 8 env CLASSPATH="$MODDIR/companion/LetAppsLive.apk" /system/bin/app_process /system/bin io.github.dtingley11.letappslive.PolicyCompiler "$1/original.xml" "$1/base.xml" "$1/remote-base.txt" "$1/remote-custom.txt" "$1/visible.xml" "$1/apps.txt" "$1/prepared" > "$MODDIR/policy-prepare.log" 2>&1; then
        athena_error 'The device policy could not be prepared. See policy-prepare.log.'; return 1
    fi
    printf '%s\n' "$ATHENA_TARGET" > "$1/prepared/target.txt"
    athena_build_identity > "$1/prepared/build-id.txt" || return 1
    printf '%s\n' "$athena_apk" > "$1/prepared/athena-apk.txt"
    athena_hash=$(sha256sum "$athena_apk") || return 1
    printf '%s\n' "${athena_hash%% *}" > "$1/prepared/athena-apk.sha256"
    rm -rf "$MODDIR/device" "$MODDIR/system"
    mv "$1/prepared" "$MODDIR/device" || return 1
    (cd "$MODDIR" && sha256sum device/*) > "$MODDIR/device-state.sha256" || return 1
}

athena_make_policy() {
    athena_load_target || return 1
    athena_version=$(cat "$MODDIR/device/policy-version.txt") || return 1
    awk -v policy_version="$athena_version" -f "$MODDIR/generate-policy.awk" "$1" "$MODDIR/device/policy-entries.tsv" "$MODDIR/device/custom-policy.xml" > "$2/policy.xml" || return 1
    mkdir -p "$MODDIR/${ATHENA_RELATIVE%/*}" || return 1
    chmod 0644 "$2/policy.xml" || return 1
    chcon u:object_r:system_file:s0 "$2/policy.xml" || return 1
    mv "$2/policy.xml" "$MODDIR/$ATHENA_RELATIVE" || return 1
    cp "$1" "$MODDIR/covered-packages.txt" || return 1
    (cd "$MODDIR" && sha256sum "$ATHENA_RELATIVE" covered-packages.txt) > "$2/state.sha256" || return 1
    mv "$2/state.sha256" "$MODDIR/state.sha256" || return 1
}

athena_decode_packages() {
    if [ "$(head -c 3 "$1")" = ABX ]; then
        [ -x /system/bin/abx2xml ] && timeout 3 /system/bin/abx2xml "$1" - > "$2"
    else
        cp "$1" "$2"
    fi
}

athena_boot_inventory() {
    athena_decode_packages /data/system/users/0/package-restrictions.xml "$1/users.xml" || return 1
    athena_decode_packages /data/system/packages.xml "$1/packages.xml" || return 1
    awk -f "$MODDIR/package-inventory.awk" "$1/users.xml" "$1/packages.xml" > "$1/unsorted.txt" || return 1
    LC_ALL=C sort "$1/unsorted.txt" > "$1/apps.txt" || return 1
}

athena_pm_inventory() {
    /system/bin/pm list packages -3 --user 0 > "$1/pm.txt" || return 1
    awk '
        /^package:[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$/ { sub(/^package:/, ""); print; next }
        /^[[:space:]]*$/ { next }
        { bad=1 }
        END { if (bad) exit 1 }
    ' "$1/pm.txt" > "$1/unsorted.txt" || return 1
    LC_ALL=C sort -u "$1/unsorted.txt" > "$1/apps.txt" || return 1
}
