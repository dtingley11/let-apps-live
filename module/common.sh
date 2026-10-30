#!/system/bin/sh

ATHENA_TARGET=/my_product/etc/extension/sys_custom_clear_appfilter_list.xml
ATHENA_RELATIVE=system/my_product/etc/extension/sys_custom_clear_appfilter_list.xml
ATHENA_BUILD='PLR110_16.0.10.500(CN01)'
ATHENA_STOCK_HASH=15e07bcaf96e0f63456e0b80dd74509fc53acd5362ceece12f0540210cc1018b
ATHENA_PILOT_HASH=4961e187df22a368ffae04c4b422e78f91413c2715af2479ab33bc3654baf4e1

# Read-only compatibility check. Install mode also accepts our active overlay.
athena_check() {
    ATHENA_ERROR=
    if [ "$(getprop ro.product.model)" != PLR110 ] ||
       [ "$(getprop ro.build.version.sdk)" != 36 ] ||
       [ "$(getprop ro.build.display.id)" != "$ATHENA_BUILD" ]; then
        ATHENA_ERROR='Unsupported firmware; review and rebuild the module.'
        return 1
    fi
    if [ ! -f /data/adb/modules/mountify/metamount.sh ] ||
       [ -f /data/adb/modules/mountify/disable ] ||
       [ -f /data/adb/modules/mountify/remove ] ||
       ! grep -Eq '^[[:space:]]*mountify_mounts=2([[:space:]]*(#.*)?)?$' /data/adb/mountify/config.sh; then
        ATHENA_ERROR='The existing Mountify metamodule must be enabled in automatic mode.'
        return 1
    fi
    if ! (cd "$MODDIR" && sha256sum -c resources.sha256 >/dev/null 2>&1); then
        ATHENA_ERROR='Module resources failed their checksum check.'
        return 1
    fi
    athena_hash=$(sha256sum "$ATHENA_TARGET") || {
        ATHENA_ERROR='Cannot read the stock cleanup configuration.'
        return 1
    }
    athena_hash=${athena_hash%% *}
    if [ "$athena_hash" != "$ATHENA_STOCK_HASH" ]; then
        athena_owned=
        if [ "${1:-boot}" = install ]; then
            if [ "$athena_hash" = "$ATHENA_PILOT_HASH" ]; then
                athena_owned=yes
            elif [ -f /data/adb/modules/discord_athena_usekill/state.sha256 ]; then
                if (cd /data/adb/modules/discord_athena_usekill && sha256sum -c state.sha256 >/dev/null 2>&1); then
                    athena_previous=$(sha256sum "/data/adb/modules/discord_athena_usekill/$ATHENA_RELATIVE")
                    [ "$athena_hash" = "${athena_previous%% *}" ] && athena_owned=yes
                fi
            fi
        fi
        if [ "$athena_owned" != yes ]; then
            ATHENA_ERROR='Stock XML changed or another overlay is active; refusing to apply a stale policy.'
            return 1
        fi
    fi
    if ! (cd "$MODDIR" && sha256sum -c state.sha256 >/dev/null 2>&1); then
        ATHENA_ERROR='The existing generated policy or package manifest failed its checksum.'
        return 1
    fi
    return 0
}

athena_make_policy() {
    # $1 is a validated sorted package list; $2 is a private workspace.
    awk -f "$MODDIR/generate-policy.awk" "$1" "$MODDIR/policy-entries.tsv" \
        "$MODDIR/stock/sys_custom_clear_appfilter_list.xml" > "$2/policy.xml" || return 1
    mkdir -p "$MODDIR/system/my_product/etc/extension" || return 1
    chmod 0644 "$2/policy.xml" || return 1
    chcon u:object_r:system_file:s0 "$2/policy.xml" || return 1
    # Publish complete files only. This runs before Mountify copies the overlay.
    mv "$2/policy.xml" "$MODDIR/$ATHENA_RELATIVE" || return 1
    cp "$1" "$MODDIR/covered-packages.txt" || return 1
    (cd "$MODDIR" && sha256sum "$ATHENA_RELATIVE" covered-packages.txt) > "$2/state.sha256" || return 1
    mv "$2/state.sha256" "$MODDIR/state.sha256" || return 1
}

athena_boot_inventory() {
    # Neither PackageManager nor system_server is needed. Bound early-boot work.
    timeout 3 /system/bin/abx2xml /data/system/users/0/package-restrictions.xml - > "$1/users.xml" || return 1
    timeout 3 /system/bin/abx2xml /data/system/packages.xml - > "$1/packages.xml" || return 1
    awk -f "$MODDIR/package-inventory.awk" "$1/users.xml" "$1/packages.xml" > "$1/unsorted.txt" || return 1
    LC_ALL=C sort "$1/unsorted.txt" > "$1/apps.txt" || return 1
}

athena_pm_inventory() {
    pm list packages -3 --user 0 > "$1/pm.txt" || return 1
    # Reject unexpected/error output instead of silently publishing a partial list.
    awk '
        /^package:[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$/ { sub(/^package:/, ""); print; next }
        /^[[:space:]]*$/ { next }
        { bad=1 }
        END { if (bad) exit 1 }
    ' "$1/pm.txt" > "$1/unsorted.txt" || return 1
    LC_ALL=C sort -u "$1/unsorted.txt" > "$1/apps.txt" || return 1
}
