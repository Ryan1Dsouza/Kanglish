package org.kanglish.app

import android.content.ClipboardManager
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.widget.TextView
import com.google.android.material.switchmaterial.SwitchMaterial
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.ui.AudioCaptionActivity
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class AudioCaptionUiTest {
    @Test fun captionsAreRomanizedCopyableAndOnlineIsOptIn() {
        val controller = Robolectric.buildActivity(AudioCaptionActivity::class.java).setup()
        val activity = controller.get()
        assertFalse(activity.findViewById<SwitchMaterial>(R.id.switchAudioOnline).isChecked)
        assertFalse(activity.findViewById<View>(R.id.btnAudioStop).isEnabled)
        activity.onPartial("ನಾನು ಬರಲ್ಲ")
        assertEquals("naanu baralla", activity.findViewById<TextView>(R.id.tvAudioPartial).text.toString())
        assertFalse(activity.findViewById<View>(R.id.btnAudioCopy).isEnabled)
        activity.onFinal("ನಾನು ಬರಲ್ಲ ಇವತ್ತು")
        assertEquals(View.GONE, activity.findViewById<View>(R.id.tvAudioPartial).visibility)
        assertTrue(activity.findViewById<TextView>(R.id.tvAudioTranscript).text.toString().startsWith("naanu baralla ivattu\n"))
        assertFalse(activity.findViewById<TextView>(R.id.tvAudioTranscript).text.toString().contains("I baralla"))
        activity.findViewById<View>(R.id.btnAudioCopy).performClick()
        assertEquals("naanu baralla ivattu", activity.getSystemService(ClipboardManager::class.java).primaryClip!!.getItemAt(0).text.toString())
        capture(activity.window.decorView)
        activity.onPartial("ನಾಳೆ")
        controller.pause().stop()
        assertEquals(View.GONE, activity.findViewById<View>(R.id.tvAudioPartial).visibility)
        assertTrue(activity.findViewById<View>(R.id.btnAudioStart).isEnabled)
        controller.destroy()
    }

    private fun capture(view: View) {
        view.measure(View.MeasureSpec.makeMeasureSpec(360, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(800, View.MeasureSpec.EXACTLY))
        view.layout(0, 0, 360, 800)
        val bitmap = Bitmap.createBitmap(360, 800, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        val file = File("build/outputs/ui-preview/audio-captions.png")
        file.parentFile!!.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }
}
