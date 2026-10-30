package io.github.dtingley11.letappslive;

import android.Manifest;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.provider.Settings;
import org.json.JSONArray;
import org.json.JSONException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class PolicyStore {
    static final String KEY = "sys_not_auto_clear_notification_config_pkg_list";
    static final String GRANT = "adb shell pm grant io.github.dtingley11.letappslive android.permission.WRITE_SECURE_SETTINGS";
    static final ExecutorService WORK = Executors.newSingleThreadExecutor();
    private static final Object LOCK = new Object();
    final Context context;
    final SharedPreferences preferences;

    PolicyStore(Context context) {
        this.context = context.getApplicationContext();
        preferences = this.context.getSharedPreferences("notification_policy", Context.MODE_PRIVATE);
    }

    boolean hasPermission() {
        return context.checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS)
                == PackageManager.PERMISSION_GRANTED;
    }

    boolean automatic() { return preferences.getBoolean("automatic", false); }

    Set<String> excluded() { return savedSet("excluded"); }

    private Set<String> savedSet(String key) {
        return new HashSet<>(preferences.getStringSet(key, new HashSet<>()));
    }

    String raw() { return Settings.Global.getString(context.getContentResolver(), KEY); }

    static Set<String> parse(String raw) throws JSONException {
        Set<String> result = new TreeSet<>();
        if (raw == null || raw.trim().isEmpty()) return result;
        JSONArray array = new JSONArray(raw);
        for (int i = 0; i < array.length(); i++) {
            Object value = array.get(i);
            if (!(value instanceof String)) throw new JSONException("The stored list contains a non-text value.");
            String pkg = (String) value;
            if (pkg.isEmpty()) continue;
            if (!pkg.matches("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*"))
                throw new JSONException("The stored list contains an invalid package name.");
            result.add(pkg);
        }
        return result;
    }

    Set<String> read() throws JSONException { return parse(raw()); }

    List<ApplicationInfo> applications() {
        return context.getPackageManager().getInstalledApplications(0);
    }

    Set<String> userApps() {
        Set<String> result = new HashSet<>();
        for (ApplicationInfo info : applications()) {
            if (!PolicyEngine.isSystem(info.flags)) result.add(info.packageName);
        }
        return result;
    }

    private void checkAccess() {
        if (!hasPermission()) throw new SecurityException("Grant settings access first.");
        if (raw() == null) throw new IllegalStateException("This device does not expose the ColorOS notification setting.");
    }

    private void write(Set<String> desired) throws JSONException {
        checkAccess();
        String before = raw();
        if (parse(before).equals(desired)) return;
        // Back up the exact original string only before the first actual change.
        if (!preferences.contains("original")) {
            if (!preferences.edit().putString("original", before).commit())
                throw new IllegalStateException("Could not save the original setting.");
        }
        JSONArray json = new JSONArray(new ArrayList<>(new TreeSet<>(desired)));
        if (!Settings.Global.putString(context.getContentResolver(), KEY, json.toString()))
            throw new IllegalStateException("Android rejected the settings update.");
        if (!read().equals(desired))
            throw new IllegalStateException("The setting changed again before it could be verified. Refresh and retry.");
    }

    void change(Collection<String> packages, boolean enabled) throws JSONException {
        synchronized (LOCK) {
            Set<String> users = userApps();
            Set<String> exclusions = excluded();
            Set<String> owned = savedSet("owned");
            Set<String> current = read();
            Set<String> desired = PolicyEngine.change(current, packages, enabled);
            if (automatic()) {
                for (String pkg : packages) {
                    if (!users.contains(pkg)) continue;
                    if (enabled) {
                        exclusions.remove(pkg);
                        if (!current.contains(pkg)) owned.add(pkg);
                    } else {
                        exclusions.add(pkg);
                        owned.remove(pkg);
                    }
                }
            }
            write(desired);
            preferences.edit().putStringSet("excluded", exclusions).putStringSet("owned", owned).commit();
        }
    }

    void setAutomatic(boolean enabled) throws JSONException {
        synchronized (LOCK) {
            if (!enabled) {
                preferences.edit().putBoolean("automatic", false).commit();
                return; // Existing selections are retained when automation is switched off.
            }
            checkAccess();
            PolicyEngine.Result result = PolicyEngine.reconcile(read(), userApps(), excluded(), savedSet("owned"));
            write(result.packages);
            preferences.edit().putBoolean("automatic", true).putStringSet("owned", result.owned).commit();
        }
    }

    void reconcile() throws JSONException {
        synchronized (LOCK) {
            if (!automatic()) return;
            checkAccess();
            PolicyEngine.Result result = PolicyEngine.reconcile(read(), userApps(), excluded(), savedSet("owned"));
            write(result.packages);
            preferences.edit().putStringSet("owned", result.owned).commit();
        }
    }

    boolean hasOriginal() { return preferences.contains("original"); }

    void restoreOriginal() throws JSONException {
        synchronized (LOCK) {
            checkAccess();
            if (!hasOriginal()) return;
            String original = preferences.getString("original", "[]");
            parse(original);
            if (!Settings.Global.putString(context.getContentResolver(), KEY, original))
                throw new IllegalStateException("Android rejected the settings update.");
            if (!original.equals(raw())) throw new IllegalStateException("The original setting could not be verified.");
            preferences.edit().putBoolean("automatic", false).remove("excluded").remove("owned").commit();
        }
    }
}
