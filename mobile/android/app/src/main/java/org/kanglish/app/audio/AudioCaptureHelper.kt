package org.kanglish.app.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlin.math.sqrt

class AudioCaptureHelper(
    private val onSpeechFrame: (FloatArray) -> Unit
) {
    companion object {
        const val SAMPLE_RATE = 16000
        const val VAD_RMS_THRESHOLD = 0.008f
        const val LEADING_PAD_SAMPLES = (SAMPLE_RATE * 0.200).toInt() // 200ms leading pad (3200 samples)
        const val MAX_SPEECH_DURATION_SAMPLES = SAMPLE_RATE * 8      // Cap at 8s for fast turnaround

        fun normalizePcm(shortBuffer: ShortArray, readCount: Int): FloatArray {
            val floatChunk = FloatArray(readCount)
            for (i in 0 until readCount) {
                floatChunk[i] = (shortBuffer[i] / 32768.0f).coerceIn(-1.0f, 1.0f)
            }
            return floatChunk
        }

        fun computeRms(floatChunk: FloatArray): Float {
            if (floatChunk.isEmpty()) return 0.0f
            var sumSquares = 0.0
            for (sample in floatChunk) {
                sumSquares += sample * sample
            }
            return sqrt(sumSquares / floatChunk.size).toFloat()
        }
    }

    private var audioRecord: AudioRecord? = null
    @Volatile private var isRecording = false

    @SuppressLint("MissingPermission")
    fun startListening() {
        val minBufSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        val bufferSize = maxOf(minBufSize * 2, SAMPLE_RATE * 2)

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize
        )

        if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
            throw IllegalStateException("AudioRecord failed to initialize at 16kHz")
        }

        isRecording = true
        audioRecord?.startRecording()

        Thread {
            val shortBuffer = ShortArray(SAMPLE_RATE / 2) // 500ms chunks
            val activeSpeechBuffer = ArrayList<Float>()
            val leadingPadBuffer = ArrayDeque<Float>()
            var silenceChunks = 0

            while (isRecording) {
                val record = audioRecord ?: break
                val readCount = record.read(shortBuffer, 0, shortBuffer.size)
                if (readCount > 0) {
                    val floatChunk = normalizePcm(shortBuffer, readCount)
                    val rms = computeRms(floatChunk)

                    if (rms >= VAD_RMS_THRESHOLD) {
                        silenceChunks = 0
                        // Prepend 200ms leading audio pad when transitioning from silence to active speech
                        if (activeSpeechBuffer.isEmpty() && leadingPadBuffer.isNotEmpty()) {
                            activeSpeechBuffer.addAll(leadingPadBuffer)
                        }
                        for (sample in floatChunk) activeSpeechBuffer.add(sample)

                        // Cap max segment at 8 seconds for fast real-time turnaround
                        if (activeSpeechBuffer.size >= MAX_SPEECH_DURATION_SAMPLES) {
                            onSpeechFrame(activeSpeechBuffer.toFloatArray())
                            activeSpeechBuffer.clear()
                            leadingPadBuffer.clear()
                        }
                    } else if (activeSpeechBuffer.isNotEmpty()) {
                        silenceChunks++
                        for (sample in floatChunk) activeSpeechBuffer.add(sample)
                        // 1 second of trailing silence triggers immediate STT extraction
                        if (silenceChunks >= 2) {
                            onSpeechFrame(activeSpeechBuffer.toFloatArray())
                            activeSpeechBuffer.clear()
                            leadingPadBuffer.clear()
                            silenceChunks = 0
                        }
                    } else {
                        // Maintain rolling 200ms leading pad buffer during silence
                        for (sample in floatChunk) {
                            leadingPadBuffer.addLast(sample)
                            if (leadingPadBuffer.size > LEADING_PAD_SAMPLES) {
                                leadingPadBuffer.removeFirst()
                            }
                        }
                    }
                }
            }
        }.start()
    }

    fun stopListening() {
        isRecording = false
        audioRecord?.stop()
        audioRecord?.release()
        audioRecord = null
    }

    fun isRecording(): Boolean = isRecording
}
