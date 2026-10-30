#!/system/bin/sh

ATHENA_TARGET=/my_product/etc/extension/sys_custom_clear_appfilter_list.xml
ATHENA_RELATIVE=system/my_product/etc/extension/sys_custom_clear_appfilter_list.xml
ATHENA_BUILD='PLR110_16.0.10.500(CN01)'
ATHENA_STOCK_HASH=15e07bcaf96e0f63456e0b80dd74509fc53acd5362ceece12f0540210cc1018b

# Read-only preflight. The caller sets MODDIR to this module's directory.
athena_check() {
    ATHENA_ERROR=
    if [ "$(getprop ro.product.model)" != PLR110 ] ||
       [ "$(getprop ro.build.version.sdk)" != 36 ] ||
       [ "$(getprop ro.build.display.id)" != "$ATHENA_BUILD" ]; then
        ATHENA_ERROR='Unsupported firmware. Rebuild and review against the new firmware.'
        return 1
    fi
    if [ ! -f /data/adb/modules/mountify/metamount.sh ] ||
       [ -f /data/adb/modules/mountify/disable ] ||
       [ -f /data/adb/modules/mountify/remove ]; then
        ATHENA_ERROR='The supported Mountify metamodule must be installed and enabled.'
        return 1
    fi
    if ! grep -Eq '^[[:space:]]*mountify_mounts=2([[:space:]]*(#.*)?)?$' /data/adb/mountify/config.sh; then
        ATHENA_ERROR='Mountify must already be in automatic mode (mountify_mounts=2).'
        return 1
    fi
    if [ ! -f "$ATHENA_TARGET" ]; then
        ATHENA_ERROR='Stock ColorOS custom cleanup file is missing.'
        return 1
    fi
    athena_hash=$(sha256sum "$ATHENA_TARGET") || {
        ATHENA_ERROR='Cannot checksum the stock cleanup file.'
        return 1
    }
    if [ "${athena_hash%% *}" != "$ATHENA_STOCK_HASH" ]; then
        ATHENA_ERROR='The stock file differs. If this module is active, disable it and reboot before reinstalling.'
        return 1
    fi
    athena_expected=$(cat "$MODDIR/payload.sha256") || {
        ATHENA_ERROR='Payload checksum is missing.'
        return 1
    }
    athena_hash=$(sha256sum "$MODDIR/$ATHENA_RELATIVE") || {
        ATHENA_ERROR='Cannot checksum the module payload.'
        return 1
    }
    if [ "${athena_hash%% *}" != "$athena_expected" ]; then
        ATHENA_ERROR='Module XML payload checksum does not match.'
        return 1
    fi
    return 0
}
