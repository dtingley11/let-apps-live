package io.github.dtingley11.letappslive;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public final class RefreshReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())) return;
        PolicyStore store = new PolicyStore(context);
        if (!store.automatic() || !store.hasPermission()) return;
        PendingResult pending = goAsync();
        PolicyStore.WORK.execute(() -> {
            try { store.reconcile(); }
            catch (Exception error) { Log.w("LetAppsLive", "Notification list refresh could not complete."); }
            finally { pending.finish(); }
        });
    }
}
