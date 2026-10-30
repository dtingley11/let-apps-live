#!/system/bin/sh

MODDIR=${0%/*}
. "$MODDIR/common.sh"

if ! athena_check boot; then
    printf '%s\n' "Disabled before mounting: $ATHENA_ERROR" > "$MODDIR/status.txt"
    touch "$MODDIR/disable" "$MODDIR/skip_mount" "$MODDIR/skip_mountify"
    exit 0
fi

athena_tmp=$(mktemp -d "$MODDIR/.boot-inventory.XXXXXX") || exit 0
cleanup() {
    rm -f "$athena_tmp/users.xml" "$athena_tmp/packages.xml" "$athena_tmp/unsorted.txt" \
        "$athena_tmp/apps.txt" "$athena_tmp/policy.xml" "$athena_tmp/state.sha256"
    rmdir "$athena_tmp" 2>/dev/null
}
trap cleanup EXIT

if ! athena_boot_inventory "$athena_tmp"; then
    printf '%s\n' 'Boot inventory refresh failed or timed out. Keeping the last checksum-verified package list; use Action to check pending apps.' > "$MODDIR/status.txt"
    exit 0
fi
if ! athena_make_policy "$athena_tmp/apps.txt" "$athena_tmp"; then
    printf '%s\n' 'Policy generation failed; disabled before mounting.' > "$MODDIR/status.txt"
    touch "$MODDIR/disable" "$MODDIR/skip_mount" "$MODDIR/skip_mountify"
    exit 0
fi
athena_count=$(wc -l < "$MODDIR/covered-packages.txt")
printf 'Boot refresh complete: %s user-installed packages. Use Action to check the live policy.\n' "$athena_count" > "$MODDIR/status.txt"
