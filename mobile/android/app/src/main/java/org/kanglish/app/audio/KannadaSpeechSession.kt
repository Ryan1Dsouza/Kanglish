package org.kanglish.app.audio

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import org.kanglish.app.R

/**
 * Low-latency continuous speech recognition session for Kannada audio.
 * Reuses the SpeechRecognizer instance across utterances to eliminate the
 * 1.5s - 2.0s IPC service reconnection lag between phrases.
 */
class KannadaSpeechSession(private val context: Context, private val listener: Listener) {
    interface Listener {
        fun onState(busy: Boolean, status: Int)
        fun onPartial(text: String)
        fun onFinal(text: String)
    }

    private val handler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var generation = 0
    private var running = false
    private var online = false
    private var silentTurns = 0
    private var lastPartial = ""
    private val segments = mutableListOf<String>()
    private var recoveryAttempts = 0

    var isBusy = false
        private set

    fun start(allowOnline: Boolean) {
        if (isBusy) return
        online = allowOnline
        running = true
        silentTurns = 0
        lastPartial = ""
        recoveryAttempts = 0
        isBusy = true
        listener.onState(true, R.string.audio_connecting)

        if (!initEngine()) {
            return
        }
        restartListening(delayMs = 0)
    }

    private fun initEngine(): Boolean {
        release()
        val token = ++generation
        try {
            val engine = if (online) {
                if (!SpeechRecognizer.isRecognitionAvailable(context)) {
                    cancel(R.string.audio_no_service)
                    return false
                }
                SpeechRecognizer.createSpeechRecognizer(context)
            } else {
                if (Build.VERSION.SDK_INT < 31 || !SpeechRecognizer.isOnDeviceRecognitionAvailable(context)) {
                    cancel(R.string.audio_no_offline)
                    return false
                }
                SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
            }

            recognizer = engine
            engine.setRecognitionListener(object : RecognitionListener {
                private fun current() = token == generation && recognizer === engine

                override fun onReadyForSpeech(params: Bundle?) {
                    if (current() && running) listener.onState(true, R.string.audio_listening)
                }

                override fun onBeginningOfSpeech() {
                    if (current() && running) listener.onState(true, R.string.audio_listening)
                }

                override fun onEndOfSpeech() {
                    if (current()) listener.onState(true, R.string.audio_finishing)
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    if (!current() || !running) return
                    val text = best(partialResults).trim()
                    if (text.isNotBlank() && !isNoiseArtifact(text) && text != lastPartial) {
                        lastPartial = text
                        listener.onPartial(text)
                    }
                }

                override fun onResults(results: Bundle?) {
                    if (!current()) return
                    val text = best(results).trim()
                    if (text.isNotBlank() && !isNoiseArtifact(text)) {
                        silentTurns = 0
                        // Some providers send a cumulative final after segment callbacks.
                        val committed = segments.joinToString(" ")
                        if (segments.isEmpty()) dispatchFinal(text)
                        else if (text.startsWith("$committed ")) dispatchFinal(text.removePrefix(committed).trim())
                    } else {
                        silentTurns++
                    }
                    if (running) {
                        restartListening(delayMs = 15)
                    } else {
                        cancel()
                    }
                }

                override fun onError(error: Int) {
                    if (!current()) return
                    if (!running) {
                        cancel()
                        return
                    }
                    if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
                        silentTurns++
                        // Allow continuous listening through silence without cutting off prematurely
                        if (silentTurns > 30) {
                            cancel(R.string.audio_no_speech)
                            return
                        }
                        restartListening(delayMs = 40)
                    } else if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) {
                        if (++recoveryAttempts > 3) cancel(R.string.audio_busy_error)
                        else restartListening(delayMs = 200L * recoveryAttempts)
                    } else if (error == SpeechRecognizer.ERROR_CLIENT || error == SpeechRecognizer.ERROR_SERVER_DISCONNECTED) {
                        // Recreate recognizer on client or binder error
                        if (++recoveryAttempts > 3) { cancel(R.string.audio_recognition_error); return }
                        handler.postDelayed({
                            if (running) {
                                if (initEngine()) restartListening(delayMs = 20)
                            }
                        }, 100)
                    } else {
                        cancel(when (error) {
                            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> R.string.audio_permission_needed
                            SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED, SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE -> R.string.audio_language_unavailable
                            SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> R.string.audio_network_error
                            else -> R.string.audio_recognition_error
                        })
                    }
                }

                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}

                override fun onSegmentResults(segmentResults: Bundle) {
                    if (!current()) return
                    val text = best(segmentResults).trim()
                    if (text.isNotBlank() && !isNoiseArtifact(text)) {
                        silentTurns = 0
                        segments.add(text)
                        dispatchFinal(text)
                    }
                }

                override fun onEndOfSegmentedSession() {
                    if (!current()) return
                    if (running) restartListening(delayMs = 15) else cancel()
                }
            })

            return true
        } catch (_: SecurityException) {
            cancel(R.string.audio_permission_needed)
            return false
        } catch (_: RuntimeException) {
            cancel(R.string.audio_recognition_error)
            return false
        }
    }

    private fun dispatchFinal(text: String) {
        lastPartial = ""
        recoveryAttempts = 0
        listener.onPartial("")
        listener.onFinal(text)
    }

    private fun restartListening(delayMs: Long) {
        if (!running) return
        handler.removeCallbacksAndMessages(null)
        val action = {
            if (running) {
                try {
                    val engine = recognizer
                    segments.clear()
                    lastPartial = ""
                    if (engine != null) {
                        // Completed recognizers can be reused directly. cancel() here
                        // generates ERROR_CLIENT on some providers and creates restart loops.
                        engine.startListening(buildRequest())
                        isBusy = true
                        listener.onState(true, R.string.audio_listening)
                    } else {
                        if (initEngine()) {
                            recognizer?.startListening(buildRequest())
                            isBusy = true
                            listener.onState(true, R.string.audio_listening)
                        }
                    }
                } catch (e: Exception) {
                    Log.w("KanglishSpeech", "Restart error, reinitializing engine", e)
                    if (initEngine()) {
                        try {
                            recognizer?.startListening(buildRequest())
                            isBusy = true
                            listener.onState(true, R.string.audio_listening)
                        } catch (_: Exception) {
                            cancel(R.string.audio_recognition_error)
                        }
                    }
                }
            }
        }

        if (delayMs > 0) {
            handler.postDelayed(action, delayMs)
        } else {
            action()
        }
    }

    private fun buildRequest(): Intent {
        return Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "kn-IN")
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "kn-IN")
            putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, !online)

            // Ultra-responsive boundaries for fast conversation & audio note playback
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 100L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 500L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 400L)

            // Android 13+ segmented streaming recognition
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS)
            }
        }
    }

    fun stop() {
        if (!isBusy) return
        running = false
        handler.removeCallbacksAndMessages(null)
        listener.onState(true, R.string.audio_finishing)
        if (recognizer == null) { cancel(); return }
        try {
            recognizer?.stopListening()
            handler.postDelayed({ cancel() }, 2000)
        } catch (_: RuntimeException) { cancel() }
    }

    fun cancel(status: Int = R.string.audio_stopped) {
        running = false
        handler.removeCallbacksAndMessages(null)
        release()
        isBusy = false
        listener.onPartial("")
        listener.onState(false, status)
    }

    private fun release() {
        generation++
        val previous = recognizer
        recognizer = null
        try { previous?.cancel() } catch (_: RuntimeException) { }
        try { previous?.destroy() } catch (_: RuntimeException) { }
    }

    private fun isNoiseArtifact(text: String): Boolean {
        val t = text.trim()
        if (t.isEmpty()) return true
        if (t.matches(Regex("^[.,!?;:'\"\\-\\s]+$"))) return true
        if (t.length == 1 && (t[0] in 'a'..'z' || t[0] in 'A'..'Z')) return true
        return false
    }

    private fun best(bundle: Bundle?): String {
        val list = bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION) ?: return ""
        for (item in list) {
            val trimmed = item.trim()
            if (trimmed.isNotEmpty() && !isNoiseArtifact(trimmed)) {
                return trimmed
            }
        }
        return list.firstOrNull().orEmpty()
    }
}
