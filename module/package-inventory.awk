# Input: abx2xml output for user 0 restrictions, then global packages.xml.
# FLAG_SYSTEM is bit 0; directory names cannot distinguish updated system apps.
BEGIN { RS = ">" }
function attribute(text, key, pattern, value) {
    pattern = "[[:space:]]" key "=\"[^\"]*\""
    if (!match(text, pattern)) return ""
    value = substr(text, RSTART, RLENGTH)
    sub(/^[^=]*="/, "", value)
    sub(/"$/, "", value)
    return value
}
function valid_name(name) {
    # Framework resource packages also use single labels, e.g. android/oplus.
    return name ~ /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/
}
{
    tag = $0
    sub(/^[[:space:]]+/, "", tag)
    if (tag ~ /<!DOCTYPE|<!ENTITY/) bad = 1
}
FILENAME == ARGV[1] {
    if (tag ~ /^<package-restrictions([[:space:]]|$)/) user_open++
    if (tag ~ /^<\/package-restrictions[[:space:]]*$/) user_close++
    if (tag ~ /^<pkg[[:space:]]/) {
        name = attribute(tag, "name")
        if (!valid_name(name)) bad = 1
        if (attribute(tag, "inst") == "false" || attribute(tag, "installed") == "false") absent[name] = 1
    }
    next
}
FILENAME == ARGV[2] {
    if (tag ~ /^<packages([[:space:]]|$)/) global_open++
    if (tag ~ /^<\/packages[[:space:]]*$/) global_close++
    if (tag ~ /^<package[[:space:]]/) {
        records++
        name = attribute(tag, "name")
        flags = attribute(tag, "publicFlags")
        if (flags == "") flags = attribute(tag, "flags")
        if (name == "android") next
        if (!valid_name(name) || flags !~ /^-?[0-9]+$/) {
            bad = 1
            next
        }
        if ((flags + 0) % 2 == 0 && !absent[name]) {
            if (name !~ /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$/) bad = 1
            else selected[name] = 1
        }
    }
}
END {
    if (bad || records == 0 || user_open != 1 || user_close != 1 || global_open != 1 || global_close != 1) {
        print "Package database format is incomplete or unsupported." > "/dev/stderr"
        exit 1
    }
    for (name in selected) print name
}
