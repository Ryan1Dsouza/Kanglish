package org.kanglish.app

import android.view.accessibility.AccessibilityNodeInfo
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.overlay.KanglishAccessibilityService
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class WhatsAppHoldTest {
    @Test fun onlyKnownMessageBodyIdsAreAcceptedAndChatNamesAreIgnored() {
        val service = KanglishAccessibilityService()
        for (pkg in listOf("com.whatsapp", "com.whatsapp.w4b")) {
            val node = AccessibilityNodeInfo.obtain().apply { text = "SOURCE_FIXTURE"; isLongClickable = true }
            node.viewIdResourceName = "$pkg:id/conversation_contact_name"
            assertEquals("", service.heldMessageText(node, pkg))
            node.viewIdResourceName = "$pkg:id/message_text"
            assertEquals("SOURCE_FIXTURE", service.heldMessageText(node, pkg))
            node.viewIdResourceName = "$pkg:id/conversations_row_message"
            assertEquals("", service.heldMessageText(node, pkg))
        }
    }
}
