#!/system/bin/sh

MODDIR=${0%/*}
. "$MODDIR/common.sh"
. "$MODDIR/companion.sh"
printf '%s\n' 'Let Apps Live — read-only status'
printf 'Firmware: %s\n' "$(getprop ro.build.display.id)"
[ ! -f "$MODDIR/status.txt" ] || cat "$MODDIR/status.txt"
[ ! -f "$MODDIR/companion-status.txt" ] || cat "$MODDIR/companion-status.txt"
lal_companion_report
if [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/skip_mount" ] || [ -f "$MODDIR/skip_mountify" ]; then
    printf '%s\n' 'WARNING: a disable/mount-skip marker is present.'
fi

athena_tmp=$(mktemp -d "$MODDIR/.status.XXXXXX") || exit 1
cleanup() {
    rm -f "$athena_tmp/pm.txt" "$athena_tmp/users.xml" "$athena_tmp/packages.xml" \
        "$athena_tmp/unsorted.txt" "$athena_tmp/apps.txt" \
        "$athena_tmp/native.txt" "$athena_tmp/live.txt" "$athena_tmp/pending.txt" "$athena_tmp/missing.txt"
    rmdir "$athena_tmp" 2>/dev/null
}
trap cleanup EXIT

if ! (cd "$MODDIR" && sha256sum -c state.sha256 >/dev/null 2>&1); then
    printf '%s\n' 'ERROR: generated policy/manifest checksum mismatch.'
    exit 1
fi
if ! athena_pm_inventory "$athena_tmp"; then
    printf '%s\n' 'PackageManager query unavailable; checking persisted Android package metadata.'
    if ! athena_boot_inventory "$athena_tmp"; then
        printf '%s\n' 'ERROR: neither current package query nor persisted metadata is available.'
        exit 1
    fi
fi
LC_ALL=C comm -23 "$athena_tmp/apps.txt" "$MODDIR/covered-packages.txt" > "$athena_tmp/pending.txt"
printf 'Current user-installed apps: %s\n' "$(wc -l < "$athena_tmp/apps.txt")"
printf 'Prepared at install/last boot: %s\n' "$(wc -l < "$MODDIR/covered-packages.txt")"
printf 'New apps pending next reboot: %s\n' "$(wc -l < "$athena_tmp/pending.txt")"
head -n 15 "$athena_tmp/pending.txt"

if ! dumpsys athenaservice prockill filter_list sys_use_kill > "$athena_tmp/native.txt" 2>&1; then
    printf '%s\n' 'ERROR: cannot read the live Athena policy.'
    exit 1
fi
awk '$1 == "[USE" && $2 == "KILL]" && $4 == "-" && $5 == "true" { print $3 }' \
    "$athena_tmp/native.txt" | LC_ALL=C sort -u > "$athena_tmp/live.txt"
if [ ! -s "$athena_tmp/live.txt" ]; then
    printf '%s\n' 'NOT VERIFIED: Athena returned no readable USE KILL entries.'
    exit 1
fi
LC_ALL=C comm -23 "$MODDIR/covered-packages.txt" "$athena_tmp/live.txt" > "$athena_tmp/missing.txt"
if [ ! -s "$athena_tmp/missing.txt" ]; then
    printf '%s\n' 'PASS: every prepared user app is present in Athena’s live USE KILL map.'
else
    printf 'NOT VERIFIED: %s prepared apps are absent from the live policy.\n' "$(wc -l < "$athena_tmp/missing.txt")"
    head -n 15 "$athena_tmp/missing.txt"
    printf '%s\n' 'A reboot may be pending, or a newer ColorOS policy may have taken precedence.'
fi
