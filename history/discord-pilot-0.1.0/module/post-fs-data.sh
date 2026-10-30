#!/system/bin/sh

MODDIR=${0%/*}
. "$MODDIR/common.sh"

# KernelSU runs this before Mountify's metamount stage. On each fresh boot,
# the target is the underlying stock file, before this overlay is mounted.
if ! athena_check; then
    printf '%s\n' "Disabled before mounting: $ATHENA_ERROR" > "$MODDIR/status.txt"
    touch "$MODDIR/disable" "$MODDIR/skip_mount" "$MODDIR/skip_mountify"
    exit 0
fi

printf '%s\n' 'Preflight passed. Use the module Action after boot to verify the live Athena policy.' > "$MODDIR/status.txt"
