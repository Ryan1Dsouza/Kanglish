package org.kanglish.app.overlay

import android.app.Activity
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.FrameLayout
import android.widget.Toast

class ClipboardTrampolineActivity : Activity() {

    companion object {
        private const val TAG = "KanglishClipboard"

        fun captureIntent(context: Context) = Intent(context, ClipboardTrampolineActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
        }
    }

    private var hasDispatched = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        overridePendingTransition(0, 0)
        // A resumed activity may not yet own clipboard access. Wait for window focus.
        setContentView(FrameLayout(this))
        Log.d(TAG, "capture created task=$taskId; waiting for window focus")
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        Log.d(TAG, "capture focus=$hasFocus dispatched=$hasDispatched")
        if (hasFocus && !hasDispatched) {
            readAndDispatchClipboard()
        }
    }

    private fun readAndDispatchClipboard() {
        hasDispatched = true
        try {
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val clip = clipboard.primaryClip
            if (clip != null && clip.itemCount > 0) {
                val text = clip.getItemAt(0).text?.toString()?.trim() ?: ""
                if (text.isNotBlank()) {
                    // Log the path, never the copied message.
                    Log.d(TAG, "capture succeeded chars=${text.length}; dispatching to overlay")
                    FloatingSidebarService.translateAndShow(this, text)
                    return
                }
            }
            Log.d(TAG, "capture empty or non-text clipboard")
            Toast.makeText(this, "Copy a text message in WhatsApp, then tap the Kanglish bubble.", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Log.w(TAG, "capture failed: ${e.javaClass.simpleName}")
            Toast.makeText(this, "Could not read copied text. Open Kanglish and use Paste instead.", Toast.LENGTH_LONG).show()
        } finally {
            // Always remove only this transient task and reveal the source app immediately.
            finish()
            overridePendingTransition(0, 0)
            Log.d(TAG, "capture finished task=$taskId")
        }
    }
}
