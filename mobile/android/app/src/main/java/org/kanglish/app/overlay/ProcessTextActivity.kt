package org.kanglish.app.overlay

import android.app.Activity
import android.content.Intent
import android.os.Bundle

class ProcessTextActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        overridePendingTransition(0, 0)

        val selectedText = when (intent.action) {
            Intent.ACTION_SEND -> intent.getCharSequenceExtra(Intent.EXTRA_TEXT)
            Intent.ACTION_PROCESS_TEXT -> intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)
            else -> null
        }?.toString()?.trim().orEmpty()
        if (selectedText.isNotBlank()) {
            FloatingSidebarService.translateAndShow(this, selectedText)
        }
        finish()
        overridePendingTransition(0, 0)
    }
}
