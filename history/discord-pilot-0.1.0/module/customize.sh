#!/system/bin/sh

[ "$KSU" = true ] || abort 'This pilot supports KernelSU only.'
[ "$BOOTMODE" = true ] || abort 'Install from KernelSU Manager while Android is running.'

MODDIR=$MODPATH
. "$MODDIR/common.sh"
athena_check || abort "$ATHENA_ERROR"

ui_print 'Discord-only native Athena use_kill pilot'
ui_print 'Preserves the stock XML and adds one Discord entry.'
ui_print 'Uses the existing Mountify metamodule; reboot required.'
ui_print 'Do not lock Discord in Recents during the pilot test.'

set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm_recursive "$MODPATH/system" 0 0 0755 0644 u:object_r:system_file:s0
