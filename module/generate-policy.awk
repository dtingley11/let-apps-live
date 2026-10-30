# Inputs: sorted package names, reviewed per-package XML templates, stock XML.
BEGIN {
    FS = "\t"
    if (policy_version !~ /^[0-9]+$/ || policy_version + 0 < 1 || policy_version + 0 > 2147483647) bad = 1
}
FILENAME == ARGV[1] {
    if ($0 !~ /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$/ || seen[$0]++) {
        bad = 1
    } else names[++count] = $0
    next
}
FILENAME == ARGV[2] {
    if (NF != 2 || $2 !~ /^<p_(wl|crm|cond_wl)[[:space:]]/ || $2 !~ /use_kill="true"/) bad = 1
    templates[$1] = $2
    next
}
FILENAME == ARGV[3] {
    line = $0
    sub(/\r$/, "", line)
    if (line ~ /^[[:space:]]*<version>[0-9]+<\/version>[[:space:]]*$/) {
        versions++
        sub(/<version>[0-9]+<\/version>/, "<version>" policy_version "</version>", line)
    }
    if (line ~ /^[[:space:]]*<p_(wl|crm|cond_wl)[[:space:]]/ && match(line, /[[:space:]]pkg="[^"]*"/)) {
        pkg = substr(line, RSTART, RLENGTH)
        sub(/^[[:space:]]*pkg="/, "", pkg)
        sub(/"$/, "", pkg)
        if (pkg in seen) {
            existing[pkg] = 1
            if (line ~ /[[:space:]]use_kill="[^"]*"/) sub(/[[:space:]]use_kill="[^"]*"/, " use_kill=\"true\"", line)
            else if (line ~ /\/>[[:space:]]*$/) sub(/\/>/, " use_kill=\"true\"/>", line)
            else bad = 1
        }
    }
    if (line ~ /<\/filter-conf>/) {
        closes++
        for (i = 1; i <= count; i++) {
            name = names[i]
            if (name in existing) continue
            if (name in templates) print "    " templates[name]
            else print "    <p_cond_wl pkg=\"" name "\" use_kill=\"true\" />"
        }
    }
    print line
}
END {
    if (bad || versions != 1 || closes != 1) {
        print "Refusing to generate an invalid Athena policy." > "/dev/stderr"
        exit 1
    }
}
