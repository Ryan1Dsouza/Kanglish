package org.kanglish.app

import android.os.Bundle
import android.os.Looper
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.audio.KannadaSpeechSession
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowSpeechRecognizer
import java.time.Duration

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AudioSpeechTest {
    private class Events : KannadaSpeechSession.Listener {
        var status = 0
        var partial = ""
        val finals = mutableListOf<String>()
        override fun onState(busy: Boolean, status: Int) { this.status = status }
        override fun onPartial(text: String) { partial = text }
        override fun onFinal(text: String) { finals += text }
    }
    private fun result(text: String) = Bundle().apply {
        putStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION, arrayListOf(text))
    }
    @Test fun noOfflineRecognizerDoesNotSilentlySendAudioOnline() {
        ShadowSpeechRecognizer.setIsOnDeviceRecognitionAvailable(false)
        val events = Events()
        val session = KannadaSpeechSession(RuntimeEnvironment.getApplication(), events)
        session.start(false)
        assertFalse(session.isBusy)
        assertEquals(R.string.audio_no_offline, events.status)
        assertNull(ShadowSpeechRecognizer.getLatestSpeechRecognizer())
    }
    @Test fun finalReplacesPartialAndCancelledSessionsIgnoreLateCallbacks() {
        ShadowSpeechRecognizer.setIsOnDeviceRecognitionAvailable(true)
        val events = Events()
        val session = KannadaSpeechSession(RuntimeEnvironment.getApplication(), events)
        session.start(false)
        shadowOf(Looper.getMainLooper()).idle()
        val engine = shadowOf(ShadowSpeechRecognizer.getLatestSpeechRecognizer())
        assertEquals("kn-IN", engine.lastRecognizerIntent.getStringExtra(RecognizerIntent.EXTRA_LANGUAGE))
        assertTrue(engine.lastRecognizerIntent.getBooleanExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false))
        assertTrue(engine.lastRecognizerIntent.getBooleanExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false))
        engine.triggerOnPartialResults(result("ನಾನು"))
        assertEquals("ನಾನು", events.partial)
        engine.triggerOnResults(result("ನಾನು ಬರಲ್ಲ"))
        assertEquals(listOf("ನಾನು ಬರಲ್ಲ"), events.finals)
        session.cancel()
        assertTrue(engine.isDestroyed)
        engine.triggerOnResults(result("stale result"))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2))
        assertEquals(listOf("ನಾನು ಬರಲ್ಲ"), events.finals)
        assertFalse(session.isBusy)
    }
    @Test fun explicitStopAcceptsLastFinalWithoutRestartingMicrophone() {
        ShadowSpeechRecognizer.setIsOnDeviceRecognitionAvailable(true)
        val events = Events()
        val session = KannadaSpeechSession(RuntimeEnvironment.getApplication(), events)
        session.start(false)
        shadowOf(Looper.getMainLooper()).idle()
        val engine = shadowOf(ShadowSpeechRecognizer.getLatestSpeechRecognizer())
        session.stop()
        engine.triggerOnResults(result("ನಾಳೆ"))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(3))
        assertEquals(listOf("ನಾಳೆ"), events.finals)
        assertFalse(session.isBusy)
        assertTrue(engine.isDestroyed)
    }

    @Test fun repeatedSpokenPhrasesArePreservedWithoutRecreatingTheRecognizer() {
        ShadowSpeechRecognizer.setIsOnDeviceRecognitionAvailable(true)
        val events = Events()
        val session = KannadaSpeechSession(RuntimeEnvironment.getApplication(), events)
        session.start(false)
        shadowOf(Looper.getMainLooper()).idle()
        val recognizer = ShadowSpeechRecognizer.getLatestSpeechRecognizer()
        val engine = shadowOf(recognizer)
        engine.triggerOnResults(result("ಹಾಯ್"))
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(20))
        engine.triggerOnResults(result("ಹಾಯ್"))
        assertEquals(listOf("ಹಾಯ್", "ಹಾಯ್"), events.finals)
        assertSame(recognizer, ShadowSpeechRecognizer.getLatestSpeechRecognizer())
        session.cancel()
    }
}
