# Inputs: sorted package names, reviewed per-package XML templates, stock XML.
BEGIN { FS = "\t" }
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
    if (line ~ /<version>2025112101<\/version>/) {
        versions++
        sub(/<version>2025112101<\/version>/, "<version>2025112103</version>", line)
    }
    if (line ~ /<\/filter-conf>/) {
        closes++
        for (i = 1; i <= count; i++) {
            name = names[i]
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
