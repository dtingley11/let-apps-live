package io.github.dtingley11.letappslive;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.database.ContentObserver;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.inputmethod.InputMethodManager;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.PopupMenu;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import java.text.Collator;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<AppEntry> applications = new ArrayList<>();
    private final List<AppEntry> visible = new ArrayList<>();
    private Set<String> enabled = new HashSet<>();
    private PolicyStore store;
    private TextView status, statusDetail, count, autoDetail;
    private Switch automatic;
    private EditText search;
    private Button enableShown, disableShown, access;
    private ProgressBar progress;
    private AppAdapter adapter;
    private String query = "";
    private int filter;
    private boolean busy, writable, rendering, active, reloadRequested;
    private int background, surface, foreground, muted, accent, line;

    private final Runnable refreshLater = () -> refresh(false);
    private final ContentObserver observer = new ContentObserver(handler) {
        @Override public void onChange(boolean selfChange) {
            handler.removeCallbacks(refreshLater);
            handler.postDelayed(refreshLater, 250);
        }
    };
    private final BroadcastReceiver packages = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            refresh(true);
        }
    };

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        store = new PolicyStore(this);
        boolean dark = (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
                == Configuration.UI_MODE_NIGHT_YES;
        background = Color.parseColor(dark ? "#121613" : "#F5F7F3");
        surface = Color.parseColor(dark ? "#1D241F" : "#FFFFFF");
        foreground = Color.parseColor(dark ? "#E5EDE4" : "#18291E");
        muted = Color.parseColor(dark ? "#B0BFB2" : "#536457");
        accent = Color.parseColor(dark ? "#99D8AF" : "#286C4A");
        line = Color.parseColor(dark ? "#36433A" : "#DDE6DC");
        getWindow().setDecorFitsSystemWindows(false);
        LinearLayout root = column();
        root.setBackgroundColor(background);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars()
                    | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
            view.setPadding(dp(20) + bars.left, bars.top, dp(20) + bars.right, bars.bottom);
            return insets;
        });
        setContentView(root);

        LinearLayout heading = row();
        heading.setPadding(0, dp(16), 0, dp(14));
        TextView title = label("Let Apps Live", 29, foreground);
        title.setTypeface(null, Typeface.BOLD);
        heading.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button menu = button("More");
        menu.setContentDescription("More options");
        menu.setOnClickListener(view -> showMenu(menu));
        heading.addView(menu);
        root.addView(heading);
        TextView subtitle = label("Keep your alerts after closing apps.", 15, muted);
        subtitle.setPadding(0, 0, 0, dp(14));
        root.addView(subtitle);

        LinearLayout connection = card();
        LinearLayout connectionRow = row();
        LinearLayout connectionText = column();
        status = label("Reading settings…", 17, foreground);
        status.setTypeface(null, Typeface.BOLD);
        statusDetail = label("", 13, muted);
        statusDetail.setPadding(0, dp(5), dp(8), 0);
        connectionText.addView(status);
        connectionText.addView(statusDetail);
        connectionRow.addView(connectionText, new LinearLayout.LayoutParams(0, -2, 1));
        access = button("Set up");
        access.setOnClickListener(view -> setup());
        connectionRow.addView(access);
        connection.addView(connectionRow);
        root.addView(connection, spaced());

        LinearLayout autoCard = card();
        automatic = new Switch(this);
        automatic.setText("Automatically include user apps");
        automatic.setTextSize(16);
        automatic.setTextColor(foreground);
        automatic.setSwitchPadding(dp(12));
        automatic.setOnCheckedChangeListener((view, checked) -> {
            if (!rendering) change(() -> store.setAutomatic(checked),
                    checked ? "User-app policy enabled" : "Automatic inclusion off; selections retained");
        });
        autoCard.addView(automatic);
        autoDetail = label("", 12, muted);
        autoDetail.setPadding(0, dp(8), 0, 0);
        autoCard.addView(autoDetail);
        root.addView(autoCard, spaced());

        search = new EditText(this);
        search.setSingleLine(true);
        search.setTextSize(15);
        search.setTextColor(foreground);
        search.setHintTextColor(muted);
        search.setHint("Search apps or package names");
        search.setPadding(dp(14), dp(10), dp(14), dp(10));
        search.setBackground(shape(surface, 14));
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                query = text.toString().trim().toLowerCase(Locale.ROOT);
                filterApplications();
            }
            public void afterTextChanged(Editable text) {}
        });
        root.addView(search, spaced());

        RadioGroup filters = new RadioGroup(this);
        filters.setOrientation(LinearLayout.HORIZONTAL);
        String[] names = {"All apps", "User apps", "System"};
        for (int i = 0; i < names.length; i++) {
            RadioButton tab = new RadioButton(this);
            tab.setId(100 + i);
            tab.setText(names[i]);
            tab.setTextSize(13);
            tab.setTextColor(foreground);
            filters.addView(tab, new RadioGroup.LayoutParams(0, dp(48), 1));
        }
        filters.check(100);
        filters.setOnCheckedChangeListener((group, id) -> {
            filter = id - 100;
            filterApplications();
        });
        root.addView(filters);
        LinearLayout controls = row();
        count = label("Loading apps…", 12, muted);
        controls.addView(count, new LinearLayout.LayoutParams(0, -2, 1));
        enableShown = button("Enable shown");
        disableShown = button("Disable shown");
        enableShown.setTextSize(11);
        disableShown.setTextSize(11);
        enableShown.setOnClickListener(view -> bulk(true));
        disableShown.setOnClickListener(view -> bulk(false));
        controls.addView(enableShown);
        controls.addView(disableShown);
        root.addView(controls);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setIndeterminate(true);
        root.addView(progress, new LinearLayout.LayoutParams(-1, dp(3)));
        ListView list = new ListView(this);
        list.setDivider(null);
        list.setFastScrollEnabled(true);
        list.setClipToPadding(false);
        list.setPadding(0, dp(5), 0, dp(12));
        list.setBackgroundColor(background);
        adapter = new AppAdapter();
        list.setAdapter(adapter);
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));
        list.setOnItemClickListener((parent, view, position, id) -> {
            if (writable && !busy) {
                AppEntry app = visible.get(position);
                boolean next = !enabled.contains(app.pkg);
                change(() -> store.change(Collections.singleton(app.pkg), next), "Saved");
            }
        });
        list.setOnItemLongClickListener((parent, view, position, id) -> {
            startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:" + visible.get(position).pkg)));
            return true;
        });
    }

    @Override protected void onStart() {
        super.onStart();
        active = true;
        getContentResolver().registerContentObserver(Settings.Global.getUriFor(PolicyStore.KEY), false, observer);
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_PACKAGE_ADDED);
        filter.addAction(Intent.ACTION_PACKAGE_REMOVED);
        filter.addAction(Intent.ACTION_PACKAGE_CHANGED);
        filter.addDataScheme("package");
        registerReceiver(packages, filter, Context.RECEIVER_NOT_EXPORTED);
    }

    @Override protected void onResume() {
        super.onResume();
        refresh(true);
    }

    @Override protected void onStop() {
        active = false;
        handler.removeCallbacks(refreshLater);
        getContentResolver().unregisterContentObserver(observer);
        unregisterReceiver(packages);
        super.onStop();
    }

    private void refresh(boolean reconcile) {
        if (busy) { reloadRequested = true; return; }
        setBusy(true);
        PolicyStore.WORK.execute(() -> {
            List<AppEntry> loaded = new ArrayList<>();
            Set<String> current = new HashSet<>();
            String error = null;
            boolean hasPermission = store.hasPermission();
            boolean supported = false;
            try {
                supported = store.raw() != null;
                if (reconcile && hasPermission && supported) store.reconcile();
                current = store.read();
            } catch (Exception failure) { error = failure.getMessage(); }
            try {
                PackageManager pm = getPackageManager();
                for (ApplicationInfo info : store.applications()) {
                    loaded.add(new AppEntry(info, String.valueOf(pm.getApplicationLabel(info))));
                }
                Collator collator = Collator.getInstance();
                loaded.sort((a, b) -> {
                    int order = collator.compare(a.name, b.name);
                    return order != 0 ? order : a.pkg.compareTo(b.pkg);
                });
            } catch (Exception failure) { error = failure.getMessage(); }
            final Set<String> result = current;
            final String message = error;
            final boolean available = supported;
            handler.post(() -> {
                if (isDestroyed()) return;
                applications.clear();
                applications.addAll(loaded);
                enabled = result;
                writable = hasPermission && available && message == null;
                rendering = true;
                automatic.setChecked(store.automatic());
                rendering = false;
                status.setText(!hasPermission ? "Settings access needed"
                        : !available ? "ColorOS setting not found"
                        : message != null ? "Setting needs attention" : "Ready · " + enabled.size() + " listed");
                statusDetail.setText(!hasPermission ? "Install the module or use ADB setup."
                        : !available ? "This ROM does not expose the notification retention list."
                        : message != null ? message : "Listed apps can retain alerts during ColorOS cleanup.");
                access.setText(hasPermission ? "Details" : "Set up");
                int overrides = store.excluded().size();
                autoDetail.setText("Adds user apps on open and permitted boot refreshes. System apps stay manual."
                        + (overrides > 0 ? " " + overrides + " excluded." : ""));
                filterApplications();
                setBusy(false);
                if (reloadRequested && active) {
                    reloadRequested = false;
                    refresh(false);
                }
            });
        });
    }

    private void setBusy(boolean value) {
        busy = value;
        if (progress == null) return;
        access.setEnabled(!value);
        progress.setVisibility(value ? View.VISIBLE : View.INVISIBLE);
        automatic.setEnabled(!value && writable);
        enableShown.setEnabled(!value && writable && !visible.isEmpty());
        disableShown.setEnabled(!value && writable && !visible.isEmpty());
        adapter.notifyDataSetChanged();
    }

    private void filterApplications() {
        visible.clear();
        for (AppEntry app : applications) {
            if (filter == 1 && app.system || filter == 2 && !app.system) continue;
            if (!query.isEmpty() && !app.name.toLowerCase(Locale.ROOT).contains(query)
                    && !app.pkg.toLowerCase(Locale.ROOT).contains(query)) continue;
            visible.add(app);
        }
        count.setText(visible.size() + " shown");
        enableShown.setEnabled(!busy && writable && !visible.isEmpty());
        disableShown.setEnabled(!busy && writable && !visible.isEmpty());
        adapter.notifyDataSetChanged();
    }

    interface Operation { void run() throws Exception; }

    private void change(Operation operation, String success) {
        if (busy) return;
        setBusy(true);
        PolicyStore.WORK.execute(() -> {
            String message;
            try { operation.run(); message = success; }
            catch (Exception failure) { message = "Not saved: " + failure.getMessage(); }
            final String result = message;
            handler.post(() -> {
                if (isDestroyed()) return;
                Toast.makeText(this, result, Toast.LENGTH_LONG).show();
                setBusy(false);
                refresh(false);
            });
        });
    }

    private void bulk(boolean next) {
        Set<String> targets = new HashSet<>();
        for (AppEntry app : visible) targets.add(app.pkg);
        new AlertDialog.Builder(this)
                .setTitle((next ? "Enable " : "Disable ") + targets.size() + " shown apps?")
                .setMessage("This changes only the apps in the current filter and search results.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton(next ? "Enable" : "Disable", (dialog, which) ->
                        change(() -> store.change(targets, next), "Saved " + targets.size() + " apps"))
                .show();
    }

    private void setup() {
        if (store.hasPermission()) {
            new AlertDialog.Builder(this).setTitle("Settings access is ready")
                    .setMessage("Settings access is granted and normally survives reboots and app updates.\n\nThis app needs no root authorization or Shizuku.")
                    .setPositiveButton("Done", null)
                    .setNeutralButton("ADB instructions", (dialog, which) -> adbSetup()).show();
            return;
        }
        new AlertDialog.Builder(this).setTitle("Install the companion module")
                .setMessage("Install the Let Apps Live module in KernelSU and reboot. The module grants access; this app needs no Superuser authorization.\n\nCheck the module's Action report if access is still missing.")
                .setPositiveButton("Done", null)
                .setNeutralButton("Use ADB instead", (dialog, which) -> adbSetup())
                .setNegativeButton("Cancel", null).show();
    }

    private void adbSetup() {
        String text = "Run once from a computer with USB debugging enabled:\n\n";
        text += PolicyStore.GRANT + "\n\nIf ColorOS blocks the grant, use the bundled module instead.";
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Settings access")
                .setMessage(text).setPositiveButton("Done", null)
                .setNeutralButton("Copy command", (d, which) -> {
                    ClipboardManager clipboard = (ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
                    clipboard.setPrimaryClip(ClipData.newPlainText("ADB permission command", PolicyStore.GRANT));
                }).create();
        dialog.show();
        TextView message = dialog.findViewById(android.R.id.message);
        if (message != null) message.setTextIsSelectable(true);
    }

    private void showMenu(View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add(0, 1, 0, "Refresh now");
        menu.getMenu().add(0, 2, 1, "Settings access");
        menu.getMenu().add(0, 3, 2, "Restore original list").setEnabled(store.hasOriginal() && writable && !busy);
        menu.getMenu().add(0, 4, 3, "About");
        menu.setOnMenuItemClickListener(item -> {
            if (item.getItemId() == 1) refresh(true);
            else if (item.getItemId() == 2) setup();
            else if (item.getItemId() == 3) new AlertDialog.Builder(this)
                    .setTitle("Restore the original list?")
                    .setMessage("Restores the value saved before this app's first change and turns off automatic inclusion.")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Restore", (dialog, which) -> change(store::restoreOriginal, "Original list restored"))
                    .show();
            else new AlertDialog.Builder(this).setTitle("Let Apps Live · 0.2.1")
                    .setMessage("Manages ColorOS's notification retention list.\n\nThe module handles installation and access. No app root access, Shizuku, network access, or background polling.\n\nSwitches show list membership. Apps can still dismiss their own alerts.\n\nShows apps installed for the current Android user.")
                    .setPositiveButton("Done", null).show();
            return true;
        });
        menu.show();
    }

    private final class AppAdapter extends BaseAdapter {
        public int getCount() { return visible.size(); }
        public Object getItem(int position) { return visible.get(position); }
        public long getItemId(int position) { return position; }
        public View getView(int position, View recycled, ViewGroup parent) {
            Holder holder;
            if (recycled == null) {
                LinearLayout item = row();
                item.setMinimumHeight(dp(84));
                item.setPadding(dp(4), dp(9), dp(2), dp(9));
                ImageView icon = new ImageView(MainActivity.this);
                icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
                item.addView(icon, new LinearLayout.LayoutParams(dp(38), dp(38)));
                LinearLayout words = column();
                words.setPadding(dp(12), 0, dp(8), 0);
                TextView name = label("", 15, foreground);
                name.setMaxLines(2);
                TextView pkg = label("", 11, muted);
                pkg.setMaxLines(2);
                words.addView(name);
                words.addView(pkg);
                item.addView(words, new LinearLayout.LayoutParams(0, -2, 1));
                Switch toggle = new Switch(MainActivity.this);
                toggle.setFocusable(false);
                toggle.setClickable(false);
                item.addView(toggle);
                holder = new Holder(icon, name, pkg, toggle);
                item.setTag(holder);
                recycled = item;
            } else holder = (Holder)recycled.getTag();
            AppEntry app = visible.get(position);
            holder.name.setText(app.name);
            holder.pkg.setText(app.pkg + (app.system ? " · System" : ""));
            holder.toggle.setChecked(enabled.contains(app.pkg));
            holder.toggle.setEnabled(writable && !busy);
            holder.toggle.setContentDescription("Preserve " + app.name + " notifications");
            try { holder.icon.setImageDrawable(app.info.loadIcon(getPackageManager())); }
            catch (Exception ignored) { holder.icon.setImageResource(android.R.drawable.sym_def_app_icon); }
            return recycled;
        }
    }

    private static final class AppEntry {
        final ApplicationInfo info;
        final String pkg, name;
        final boolean system;
        AppEntry(ApplicationInfo info, String name) {
            this.info = info;
            this.pkg = info.packageName;
            this.name = name;
            system = PolicyEngine.isSystem(info.flags);
        }
    }

    private static final class Holder {
        final ImageView icon;
        final TextView name, pkg;
        final Switch toggle;
        Holder(ImageView icon, TextView name, TextView pkg, Switch toggle) {
            this.icon = icon; this.name = name; this.pkg = pkg; this.toggle = toggle;
        }
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private LinearLayout row() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(Gravity.CENTER_VERTICAL);
        return layout;
    }

    private LinearLayout card() {
        LinearLayout layout = column();
        layout.setPadding(dp(16), dp(14), dp(16), dp(14));
        layout.setBackground(shape(surface, 18));
        return layout;
    }

    private GradientDrawable shape(int color, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(radius));
        shape.setStroke(dp(1), line);
        return shape;
    }

    private TextView label(String value, int size, int color) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(color);
        return text;
    }

    private Button button(String value) {
        Button button = new Button(this);
        button.setText(value);
        button.setAllCaps(false);
        button.setTextSize(13);
        button.setTextColor(accent);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(dp(10), 0, dp(10), 0);
        return button;
    }

    private LinearLayout.LayoutParams spaced() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.bottomMargin = dp(10);
        return params;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
