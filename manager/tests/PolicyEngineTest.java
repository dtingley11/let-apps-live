package io.github.dtingley11.letappslive;

import java.util.Set;

public final class PolicyEngineTest {
    public static void main(String[] args) {
        Set<String> nativeEntries = Set.of("com.vendor.native", "com.example.preexisting");
        PolicyEngine.Result added = PolicyEngine.reconcile(nativeEntries,
                Set.of("com.example.first", "com.example.preexisting"), Set.of(), Set.of());
        assert added.packages.equals(Set.of("com.vendor.native", "com.example.preexisting", "com.example.first"));
        assert added.owned.equals(Set.of("com.example.first"));

        PolicyEngine.Result installed = PolicyEngine.reconcile(added.packages,
                Set.of("com.example.first", "com.example.new", "com.example.preexisting"), Set.of(), added.owned);
        assert installed.packages.contains("com.example.new");

        PolicyEngine.Result removed = PolicyEngine.reconcile(installed.packages,
                Set.of("com.example.new"), Set.of(), installed.owned);
        assert !removed.packages.contains("com.example.first");
        assert removed.packages.contains("com.example.preexisting"); // Never owned; preserve vendor/user entries.
        assert removed.packages.contains("com.vendor.native");

        PolicyEngine.Result excluded = PolicyEngine.reconcile(installed.packages,
                Set.of("com.example.first", "com.example.new"), Set.of("com.example.first"), installed.owned);
        assert !excluded.packages.contains("com.example.first");
        assert excluded.packages.contains("com.example.new");
        assert !excluded.owned.contains("com.example.first");

        assert PolicyEngine.change(installed.packages, Set.of("com.example.new"), false)
                .contains("com.vendor.native");
        assert !PolicyEngine.change(installed.packages, Set.of("com.example.new"), false)
                .contains("com.example.new");
        assert PolicyEngine.change(Set.of(), Set.of("android", "com.android.settings"), true)
                .equals(Set.of("android", "com.android.settings"));

        assert PolicyEngine.isSystem(1);
        assert PolicyEngine.isSystem(129); // Updated system app, even when installed under /data/app.
        assert PolicyEngine.isSystem(-1605714235);
        assert !PolicyEngine.isSystem(0);
        assert !PolicyEngine.isSystem(-2147483648);
        System.out.println("PASS: native-entry preservation, install/removal, ownership, exclusions, scoped edits, system app classification.");
    }
}
