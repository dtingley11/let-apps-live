package io.github.dtingley11.letappslive;

import java.util.Collection;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeSet;

/** Platform-independent policy: preserve unrelated entries and respect explicit exceptions. */
public final class PolicyEngine {
    private PolicyEngine() {}

    public static final class Result {
        public final Set<String> packages;
        public final Set<String> owned;

        Result(Set<String> packages, Set<String> owned) {
            this.packages = packages;
            this.owned = owned;
        }
    }

    public static Result reconcile(Collection<String> current, Set<String> userApps,
                                   Set<String> excluded, Set<String> previouslyOwned) {
        Set<String> desired = new TreeSet<>(current);
        Set<String> owned = new HashSet<>(previouslyOwned);
        for (String pkg : previouslyOwned) {
            if (!userApps.contains(pkg)) {
                desired.remove(pkg);
                owned.remove(pkg);
            }
        }
        for (String pkg : userApps) {
            if (excluded.contains(pkg)) {
                desired.remove(pkg);
                owned.remove(pkg);
            } else if (desired.add(pkg)) {
                owned.add(pkg);
            }
        }
        return new Result(desired, owned);
    }

    public static Set<String> change(Collection<String> current, Collection<String> targets,
                                     boolean enabled) {
        Set<String> result = new TreeSet<>(current);
        if (enabled) result.addAll(targets);
        else result.removeAll(targets);
        return result;
    }

    public static boolean isSystem(int applicationFlags) {
        return (applicationFlags & 1) != 0;
    }
}
