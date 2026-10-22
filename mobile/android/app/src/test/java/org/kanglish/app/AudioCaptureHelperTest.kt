package org.kanglish.app

import org.junit.Assert.*
import org.junit.Test
import org.kanglish.app.audio.AudioCaptureHelper
import kotlin.math.abs

class AudioCaptureHelperTest {

    @Test
    fun testPcmNormalizationRange() {
        val shorts = shortArrayOf(Short.MIN_VALUE, -16384, 0, 16384, Short.MAX_VALUE)
        val floats = AudioCaptureHelper.normalizePcm(shorts, shorts.size)

        assertEquals(5, floats.size)
        assertEquals(-1.0f, floats[0], 0.0001f)
        assertEquals(-0.5f, floats[1], 0.0001f)
        assertEquals(0.0f, floats[2], 0.0001f)
        assertEquals(0.5f, floats[3], 0.001f)
        assertTrue(floats[4] in 0.99f..1.0f)

        for (sample in floats) {
            assertTrue("Sample must be in [-1.0, 1.0]", sample in -1.0f..1.0f)
        }
    }

    @Test
    fun testSilenceVsSpeechRmsCalculation() {
        // Pure silence
        val silentFloats = FloatArray(1600) { 0.0f }
        val silentRms = AudioCaptureHelper.computeRms(silentFloats)
        assertEquals(0.0f, silentRms, 0.00001f)
        assertTrue("Silent RMS should be below threshold", silentRms < AudioCaptureHelper.VAD_RMS_THRESHOLD)

        // Low background noise below 0.008f threshold
        val lowNoiseFloats = FloatArray(1600) { 0.003f }
        val lowNoiseRms = AudioCaptureHelper.computeRms(lowNoiseFloats)
        assertTrue("Low noise RMS should be below threshold", lowNoiseRms < AudioCaptureHelper.VAD_RMS_THRESHOLD)

        // Speech signal above 0.008f threshold
        val speechFloats = FloatArray(1600) { if (it % 2 == 0) 0.15f else -0.15f }
        val speechRms = AudioCaptureHelper.computeRms(speechFloats)
        assertTrue("Speech RMS should exceed threshold", speechRms >= AudioCaptureHelper.VAD_RMS_THRESHOLD)
    }

    @Test
    fun testAudioConfigConstants() {
        assertEquals(16000, AudioCaptureHelper.SAMPLE_RATE)
        assertEquals(0.008f, AudioCaptureHelper.VAD_RMS_THRESHOLD, 0.0001f)
        assertEquals(3200, AudioCaptureHelper.LEADING_PAD_SAMPLES) // 200ms at 16kHz
        assertEquals(16000 * 8, AudioCaptureHelper.MAX_SPEECH_DURATION_SAMPLES) // 8s cap
    }
}
