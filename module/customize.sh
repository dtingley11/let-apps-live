#!/system/bin/sh

[ "$KSU" = true ] || abort 'Install with KernelSU Manager.'
[ "$BOOTMODE" = true ] || abort 'Install while Android is running.'
MODDIR=$MODPATH
. "$MODDIR/common.sh"
athena_check_platform || abort "$ATHENA_ERROR"

athena_tmp=$(mktemp -d "$MODPATH/.install-inventory.XXXXXX") || abort 'Cannot prepare the package inventory.'
cleanup() { rm -rf "$athena_tmp"; }
trap cleanup EXIT
athena_boot_inventory "$athena_tmp" || abort 'Cannot decode a complete Android user-app inventory.'
if ! athena_prepare_device "$athena_tmp"; then
    [ ! -f "$MODDIR/policy-prepare.log" ] || cat "$MODDIR/policy-prepare.log"
    abort "${ATHENA_ERROR:-Cannot prepare the device policy.}"
fi
athena_make_policy "$athena_tmp/apps.txt" "$athena_tmp" || abort 'Cannot generate the app policy.'

set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm_recursive "$MODPATH/system" 0 0 0755 0644 u:object_r:system_file:s0
athena_count=$(wc -l < "$MODPATH/covered-packages.txt")
ui_print "Prepared cleanup exceptions for $athena_count user apps."
ui_print 'Reboot to activate the module.'
. "$MODPATH/companion.sh"
if lal_companion_sync; then
    ui_print 'Companion app and settings permission are ready.'
else
    ui_print 'Companion setup incomplete. Check Action after reboot.'
fi
