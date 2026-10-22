package org.kanglish.app

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.overlay.ClipboardTrampolineActivity
import org.kanglish.app.overlay.FloatingSidebarService
import org.kanglish.app.overlay.ProcessTextActivity
import org.kanglish.app.ui.MainActivity
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowSettings

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28, 35])
class ClipboardEntryTest {
    private val app get() = RuntimeEnvironment.getApplication()

    @Before fun setup() { ShadowSettings.setCanDrawOverlays(true) }

    @Test fun resumeDoesNotConsumeClipboardBeforeFocusAndFocusDispatchesOnce() {
        val text = "Copied message\nSecond line 🙂"
        app.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("test", text))
        val controller = Robolectric.buildActivity(ClipboardTrampolineActivity::class.java).create().start().resume()
        val activity = controller.get()
        assertFalse(activity.isFinishing)
        assertNull(shadowOf(app).nextStartedService)
        activity.onWindowFocusChanged(false)
        assertFalse(activity.isFinishing)
        activity.onWindowFocusChanged(true)
        assertTrue(activity.isFinishing)
        assertEquals(text, shadowOf(app).nextStartedService.getStringExtra(FloatingSidebarService.EXTRA_TEXT))
        activity.onWindowFocusChanged(true)
        assertNull(shadowOf(app).nextStartedService)
        controller.pause().stop().destroy()
    }

    @Test fun emptyClipboardDoesNotStartTranslation() {
        app.getSystemService(ClipboardManager::class.java).clearPrimaryClip()
        val controller = Robolectric.buildActivity(ClipboardTrampolineActivity::class.java).create().start().resume()
        controller.get().onWindowFocusChanged(true)
        assertTrue(controller.get().isFinishing)
        assertNull(shadowOf(app).nextStartedService)
        controller.pause().stop().destroy()
    }

    @Test fun selectedTextOpensAppWhenOverlayPermissionIsMissing() {
        ShadowSettings.setCanDrawOverlays(false)
        val source = Intent(Intent.ACTION_PROCESS_TEXT).putExtra(Intent.EXTRA_PROCESS_TEXT, "Selected message")
        val controller = Robolectric.buildActivity(ProcessTextActivity::class.java, source).create()
        val launched = shadowOf(controller.get()).nextStartedActivity
        assertEquals(MainActivity::class.java.name, launched.component?.className)
        assertEquals("Selected message", launched.getStringExtra(FloatingSidebarService.EXTRA_TEXT))
        assertNull(shadowOf(app).nextStartedService)
        controller.destroy()
    }

    @Test fun sharedTextKeepsAllLines() {
        val text = "First line\nSecond line"
        val source = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
        val controller = Robolectric.buildActivity(ProcessTextActivity::class.java, source).create()
        assertEquals(text, shadowOf(app).nextStartedService.getStringExtra(FloatingSidebarService.EXTRA_TEXT))
        controller.destroy()
    }
}
