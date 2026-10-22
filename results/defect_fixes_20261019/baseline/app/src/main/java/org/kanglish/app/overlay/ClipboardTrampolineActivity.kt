package org.kanglish.app.overlay

import android.app.Activity
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import android.widget.FrameLayout
import android.widget.Toast

class ClipboardTrampolineActivity : Activity() {

    private var hasDispatched = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        overridePendingTransition(0, 0)
        // A resumed activity may not yet own clipboard access. Wait for window focus.
        setContentView(FrameLayout(this))
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
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
                    FloatingSidebarService.translateAndShow(this, text)
                    finish()
                    overridePendingTransition(0, 0)
                    return
                }
            }
            Toast.makeText(this, "Copy a text message in WhatsApp, then tap the Kanglish bubble.", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Toast.makeText(this, "Could not read copied text. Open Kanglish and use Paste instead.", Toast.LENGTH_LONG).show()
        }
        finish()
        overridePendingTransition(0, 0)
    }
}
