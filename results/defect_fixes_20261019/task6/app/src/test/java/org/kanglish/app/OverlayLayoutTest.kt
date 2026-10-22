package org.kanglish.app

import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.LayoutInflater
import android.view.View
import android.widget.TextView
import androidx.appcompat.view.ContextThemeWrapper
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.overlay.MaxHeightScrollView
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class OverlayLayoutTest {
    private fun panel(text: String): View {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_Kanglish)
        val view = LayoutInflater.from(context).inflate(R.layout.layout_floating_sidebar, null)
        view.findViewById<View>(R.id.pillHandle).visibility = View.GONE
        view.findViewById<View>(R.id.panelExpanded).visibility = View.VISIBLE
        view.findViewById<TextView>(R.id.tvFloatingOriginal).text = "Sample input"
        view.findViewById<TextView>(R.id.tvFloatingTranslated).text = text
        view.measure(View.MeasureSpec.makeMeasureSpec(360, View.MeasureSpec.AT_MOST), View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED))
        view.layout(0, 0, view.measuredWidth, view.measuredHeight)
        return view
    }

    @Test fun shortMessagesWrapWithoutScrolling() {
        val view = panel("Sample output")
        val scroll = view.findViewById<MaxHeightScrollView>(R.id.panelScroll)
        assertTrue("Short panel height: ${view.height}", view.height < 340)
        assertTrue(scroll.height < scroll.maxHeightPx)
        assertFalse(scroll.canScrollVertically(1))
        capture(view, "overlay-short")
    }

    @Test fun longMessagesScrollWithinTheHeightCap() {
        val view = panel("A line of sample text.\n".repeat(100))
        val scroll = view.findViewById<MaxHeightScrollView>(R.id.panelScroll)
        assertEquals(scroll.maxHeightPx, scroll.height)
        assertTrue(scroll.canScrollVertically(1))
        assertTrue(view.height <= 400)
        capture(view, "overlay-long")
    }

    private fun capture(view: View, name: String) {
        val image = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(image))
        val output = File("build/outputs/ui-preview/$name.png")
        output.parentFile!!.mkdirs()
        output.outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
        image.recycle()
    }
}
