#!/system/bin/sh

MODDIR=${0%/*}
. "$MODDIR/common.sh"

printf '%s\n' 'Discord Athena use_kill: read-only status'
printf 'Firmware: %s\n' "$(getprop ro.build.display.id)"
if [ -f "$MODDIR/status.txt" ]; then
    cat "$MODDIR/status.txt"
fi
if [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/skip_mount" ] || [ -f "$MODDIR/skip_mountify" ]; then
    printf '%s\n' 'WARNING: a disable/mount-skip marker is present. Review before testing.'
fi

athena_live=$(dumpsys athenaservice prockill filter_list sys_use_kill 2>&1)
if printf '%s\n' "$athena_live" | tr -d '\r' | grep -q '^\[USE KILL\] com\.discord - true$'; then
    printf '%s\n' 'PASS: live Athena USE KILL list contains com.discord=true.'
else
    printf '%s\n' 'NOT VERIFIED: Discord is absent from the live USE KILL list, or Athena diagnostics failed.'
    printf '%s\n' 'Do not infer success from installation alone; a newer downloaded ColorOS policy may take precedence.'
fi

printf '\n%s\n' 'Discord package state (look for stopped=false after opening once):'
dumpsys package com.discord | grep -m 1 'User 0:'
printf '\n%s\n' 'Recent Discord push delivery results, if available (not message content):'
dumpsys activity service com.google.android.gms/.gcm.GcmService 2>/dev/null |
    grep -E '(Successful broadcast to|Failed to broadcast to stopped app) com\.discord ' |
    tail -n 8
printf '\n%s\n' 'Rollback: disable/remove this module in KernelSU Manager, then reboot.'
