#!/system/bin/sh

MODDIR=${0%/*}
. "$MODDIR/common.sh"
. "$MODDIR/companion.sh"

# One bounded boot task, not a persistent service. Never call PackageManager in
# post-fs-data; wait until Android is ready, then exit after companion setup.
lal_attempt=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    if [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ]; then exit 0; fi
    lal_attempt=$((lal_attempt + 1))
    if [ "$lal_attempt" -ge 90 ]; then
        printf '%s\n' 'Companion setup deferred: Android did not finish booting within three minutes.' > "$MODDIR/companion-status.txt"
        exit 0
    fi
    sleep 2
done
lal_companion_sync
