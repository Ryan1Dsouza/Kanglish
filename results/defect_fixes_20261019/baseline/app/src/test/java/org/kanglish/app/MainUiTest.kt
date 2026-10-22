package org.kanglish.app

import android.graphics.Bitmap
import android.graphics.Canvas
import android.content.ClipboardManager
import android.content.ClipData
import android.view.LayoutInflater
import android.widget.EditText
import androidx.appcompat.view.ContextThemeWrapper
import android.os.Looper
import android.view.View
import com.google.android.material.tabs.TabLayout
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.ui.MainActivity
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class MainUiTest {
    @Test fun translationIsTheLandingPageAndSettingsAreSeparate() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val activity = controller.get()
        val tabs = activity.findViewById<TabLayout>(R.id.tabLayout)
        assertEquals(3, tabs.tabCount)
        assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.viewImportTab).visibility)
        assertEquals(View.GONE, activity.findViewById<View>(R.id.viewModelTab).visibility)
        capture(activity.window.decorView, "translate")
        tabs.getTabAt(1)!!.select()
        assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.viewChatTab).visibility)
        capture(activity.window.decorView, "chats")
        tabs.getTabAt(2)!!.select()
        assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.viewModelTab).visibility)
        assertEquals(View.GONE, activity.findViewById<View>(R.id.cloudSettings).visibility)
        capture(activity.window.decorView, "settings")
        val overlay = LayoutInflater.from(ContextThemeWrapper(activity, R.style.Theme_Kanglish))
            .inflate(R.layout.layout_floating_sidebar, null)
        overlay.findViewById<View>(R.id.pillHandle).visibility = View.GONE
        overlay.findViewById<View>(R.id.panelExpanded).visibility = View.VISIBLE
        capture(overlay, "overlay")
        controller.pause().stop().destroy()
    }

    @Test fun homePastePreservesMultilineTextAndClearRemovesIt() {
        val controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        val activity = controller.get()
        val text = "First copied line\nSecond copied line 🙂"
        activity.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("test", text))
        activity.findViewById<View>(R.id.btnPasteClipboard).performClick()
        assertEquals(text, activity.findViewById<EditText>(R.id.etPasteInput).text.toString())
        activity.findViewById<View>(R.id.btnClearPasteText).performClick()
        assertEquals("", activity.findViewById<EditText>(R.id.etPasteInput).text.toString())
        controller.pause().stop().destroy()
    }

    private fun capture(view: View, name: String) {
        shadowOf(Looper.getMainLooper()).idle()
        view.measure(View.MeasureSpec.makeMeasureSpec(360, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(800, View.MeasureSpec.EXACTLY))
        view.layout(0, 0, 360, 800)
        val bitmap = Bitmap.createBitmap(360, 800, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        val file = File("build/outputs/ui-preview/$name.png")
        file.parentFile!!.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }
}
