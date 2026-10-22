package org.kanglish.app.overlay

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.text.TextUtils
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

class KanglishAccessibilityService : AccessibilityService() {

    companion object {
        var isRunning = false
            private set

        fun isEnabled(context: Context): Boolean {
            val expectedServiceName = "${context.packageName}/${KanglishAccessibilityService::class.java.canonicalName}"
            val enabledServices = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false

            val colonSplitter = TextUtils.SimpleStringSplitter(':')
            colonSplitter.setString(enabledServices)
            while (colonSplitter.hasNext()) {
                val componentName = colonSplitter.next()
                if (componentName.equals(expectedServiceName, ignoreCase = true) ||
                    (componentName.contains(context.packageName) && componentName.contains("KanglishAccessibilityService"))
                ) {
                    return true
                }
            }
            return false
        }

        fun openSettings(context: Context) {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        isRunning = true
    }

    private val ignoredLabels = setOf(
        "reply", "star", "delete", "forward", "copy", "info", "share", "select", "more options",
        "search", "navigate up", "back", "call", "video call", "voice call", "attach", "camera",
        "emoji", "type a message", "message", "unread message", "unread messages"
    )

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        val pkg = event.packageName?.toString() ?: ""
        if (pkg !in setOf("com.whatsapp", "com.whatsapp.w4b", "org.telegram.messenger")) return
        if (!Settings.canDrawOverlays(this) || !FloatingSidebarService.isRunning) return
        if (pkg.contains("systemui") || pkg.contains("launcher") || pkg.contains("inputmethod")) return

        val eventType = event.eventType

        when (eventType) {
            AccessibilityEvent.TYPE_VIEW_LONG_CLICKED,
            AccessibilityEvent.TYPE_VIEW_SELECTED -> {
                val text = findMessageText(event)
                if (text.isNotBlank() && text.length in 2..500) {
                    FloatingSidebarService.translateAndShow(this, text)
                }
            }

        }
    }

    private fun findMessageText(event: AccessibilityEvent): String {
        // 1. Check event source
        val source = event.source
        if (source != null) {
            val text = extractBestCandidate(source)
            if (text.isNotBlank()) return text
        }

        // 2. Fallback to event text list
        val textList = event.text
        if (!textList.isNullOrEmpty()) {
            val joined = textList.filterNotNull().joinToString(" ").trim()
            if (joined.isNotBlank() && !isIgnoredText(joined)) {
                return joined
            }
        }

        // 3. Fallback to search in active window
        return findSelectedMessageInWindow()
    }

    private fun findSelectedMessageInWindow(): String {
        return try {
            val root = rootInActiveWindow ?: return ""
            findSelectedInTree(root)
        } catch (_: Exception) {
            ""
        }
    }

    private fun findSelectedInTree(node: AccessibilityNodeInfo?): String {
        if (node == null) return ""
        if (node.isSelected) {
            val text = extractBestCandidate(node)
            if (text.isNotBlank()) return text
        }
        for (i in 0 until node.childCount) {
            val childText = findSelectedInTree(node.getChild(i))
            if (childText.isNotBlank()) return childText
        }
        return ""
    }

    private fun extractBestCandidate(source: AccessibilityNodeInfo): String {
        val candidates = mutableListOf<String>()
        val messageBodies = mutableListOf<String>()

        fun walk(node: AccessibilityNodeInfo?, depth: Int) {
            if (node == null || depth > 8) return

            val viewId = node.viewIdResourceName?.lowercase(java.util.Locale.ROOT) ?: ""
            val text = node.text?.toString()?.trim() ?: ""

            if (text.isNotBlank() && !isIgnoredText(text)) {
                if (viewId.contains("message_text") || viewId.contains("text_content")) {
                    messageBodies.add(text)
                } else {
                    candidates.add(text)
                }
            }

            for (i in 0 until node.childCount) {
                walk(node.getChild(i), depth + 1)
            }
        }

        walk(source, 0)
        if (messageBodies.isNotEmpty()) return messageBodies.maxByOrNull { it.length }.orEmpty()
        if (candidates.isEmpty()) return ""

        // If a high-priority message_text was found, return it; otherwise return the longest text (the message body)
        return candidates.maxByOrNull { it.length } ?: ""
    }

    private fun isIgnoredText(text: String): Boolean {
        val lower = text.lowercase(java.util.Locale.ROOT).trim()
        if (ignoredLabels.contains(lower)) return true
        // Ignore pure timestamps like "10:15", "10:15 am", "10:15 pm", "10:15:22"
        if (text.matches(Regex("^\\d{1,2}:\\d{2}(:\\d{2})?(\\s*[ap]m)?$", RegexOption.IGNORE_CASE))) return true
        // Ignore numbers or punctuation only
        if (text.matches(Regex("^[\\d\\s.,!?:;\"'()\\-+/*]+$"))) return true
        return false
    }

    override fun onInterrupt() {
        isRunning = false
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
    }
}
