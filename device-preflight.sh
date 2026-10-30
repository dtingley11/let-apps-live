#!/system/bin/sh
# Run only against the /data/local/tmp review copy, never the installed module.
MODDIR=/data/local/tmp/athena-user-app-usekill-review
. "$MODDIR/common.sh"
athena_check install || { printf 'PREFLIGHT_FAILED: %s\n' "$ATHENA_ERROR"; exit 1; }
printf '%s\n' 'UPGRADE_PREFLIGHT_PASS'

athena_tmp="$MODDIR/check-work"
athena_pm_tmp="$MODDIR/pm-check"
mkdir -p "$athena_tmp" "$athena_pm_tmp" || exit 1
printf 'Inventory start uptime: '; cat /proc/uptime
athena_boot_inventory "$athena_tmp" || exit 1
printf 'Inventory end uptime: '; cat /proc/uptime
athena_pm_inventory "$athena_pm_tmp" || exit 1
diff -u "$athena_tmp/apps.txt" "$athena_pm_tmp/apps.txt" || exit 1
printf '%s\n' 'BOOT_INVENTORY_MATCHES_LIVE_PM'
athena_make_policy "$athena_tmp/apps.txt" "$athena_tmp" || exit 1
for athena_script in "$MODDIR"/*.sh; do
    /system/bin/sh -n "$athena_script" || exit 1
done
cd "$MODDIR" || exit 1
sha256sum -c state.sha256 || exit 1
printf 'Covered user apps: '; wc -l < covered-packages.txt
printf '%s\n' 'ANDROID_GENERATOR_PASS (review copy only; nothing mounted)'
