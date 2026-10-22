package org.kanglish.app.ui

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Toast
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import kotlinx.coroutines.withContext
import org.kanglish.app.audio.CaptionTranslationQueue
import org.kanglish.app.data.SourceLanguage
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.kanglish.app.R
import org.kanglish.app.audio.CaptionBuffer
import org.kanglish.app.audio.KannadaRomanizer
import org.kanglish.app.audio.KannadaSpeechSession
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.databinding.ActivityAudioCaptionsBinding
import org.kanglish.app.inference.TranslationService

class AudioCaptionActivity : AppCompatActivity(), KannadaSpeechSession.Listener {
    private lateinit var binding: ActivityAudioCaptionsBinding
    private lateinit var speech: KannadaSpeechSession
    private lateinit var translationService: TranslationService
    private val captions = CaptionBuffer()
    private lateinit var translations: CaptionTranslationQueue
    private var language = SourceLanguage.KANGLISH
    private var foreground = false
    private val microphonePermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && foreground) startListening()
        else if (!granted) binding.tvAudioStatus.setText(R.string.audio_permission_needed)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAudioCaptionsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { view, insets ->
            val edges = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.setPadding(edges.left, edges.top, edges.right, edges.bottom)
            insets
        }
        speech = KannadaSpeechSession(this, this)
        translationService = TranslationService(this)
        language = runCatching { SourceLanguage.fromId(getSharedPreferences("translation_prefs", MODE_PRIVATE)
            .getString("quick_language", SourceLanguage.KANGLISH.id)!!) }.getOrDefault(SourceLanguage.KANGLISH)
        translations = CaptionTranslationQueue(lifecycleScope, ::translatePhrase,
            completed = { id, english ->
                if (english.isNullOrBlank()) captions.setStatus(id, getString(R.string.audio_translation_unavailable))
                else captions.updatePhraseEnglish(id, english)
                renderCaptions()
            },
            skipped = { id -> captions.setStatus(id, getString(R.string.audio_translation_skipped)); renderCaptions() })
        binding.switchAudioSource.setOnCheckedChangeListener { _, _ -> renderCaptions() }

        val audioPrefs = getSharedPreferences("audio_caption_prefs", MODE_PRIVATE)
        if (audioPrefs.getBoolean("pref_audio_online", false)) {
            binding.switchAudioOnline.isChecked = true
        }
        binding.switchAudioOnline.setOnCheckedChangeListener { _, isChecked ->
            audioPrefs.edit().putBoolean("pref_audio_online", isChecked).apply()
        }

        binding.btnAudioBack.setOnClickListener { finish() }
        binding.btnAudioStart.setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) startListening()
            else microphonePermission.launch(Manifest.permission.RECORD_AUDIO)
        }
        binding.btnAudioStop.setOnClickListener { speech.stop() }
        binding.btnAudioClear.setOnClickListener { speech.cancel(); translations.clear(); captions.clear(); renderCaptions() }
        binding.btnAudioCopy.setOnClickListener {
            val copyText = captions.finalizedEnglish.ifBlank { captions.finalized }
            if (copyText.isNotBlank()) {
                getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Kannada translation", copyText))
                Toast.makeText(this, R.string.audio_copied, Toast.LENGTH_SHORT).show()
            }
        }
        binding.btnAudioPip.setOnClickListener { enterPipMode() }
        renderCaptions()
    }

    private fun enterPipMode() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            try {
                val params = android.app.PictureInPictureParams.Builder()
                    .setAspectRatio(android.util.Rational(16, 9))
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    params.setAutoEnterEnabled(true)
                }
                enterPictureInPictureMode(params.build())
            } catch (_: Exception) {
            }
        }
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (speech.isBusy && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            enterPipMode()
        }
    }

    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: android.content.res.Configuration) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        val visibility = if (isInPictureInPictureMode) View.GONE else View.VISIBLE
        binding.audioControls.visibility = visibility
        binding.audioFooter.visibility = visibility
    }

    private fun startListening() { speech.start(binding.switchAudioOnline.isChecked) }

    override fun onStart() { super.onStart(); foreground = true }
    override fun onStop() {
        foreground = false
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && isInPictureInPictureMode) {
            super.onStop()
            return
        }
        speech.cancel()
        translations.clear()
        captions.entries.filter { it.english.isBlank() }.forEach { captions.setStatus(it.id, getString(R.string.audio_translation_unavailable)) }
        renderCaptions()
        super.onStop()
    }
    override fun onDestroy() { speech.cancel(); translations.clear(); super.onDestroy() }

    override fun onState(busy: Boolean, status: Int) {
        binding.tvAudioStatus.setText(status)
        binding.btnAudioStart.isEnabled = !busy
        binding.btnAudioStop.isEnabled = busy
        binding.switchAudioOnline.isEnabled = !busy
        if (busy) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    override fun onPartial(text: String) {
        // Recognition updates must stay cheap: no dictionary scan, model or network call.
        captions.updatePartial(text)
        if (binding.tvAudioPartial.text.toString() == captions.partial) return
        binding.tvAudioPartial.text = captions.partial
        binding.tvAudioPartial.visibility = if (captions.partial.isBlank()) View.GONE else View.VISIBLE
        binding.tvAudioPartialLabel.visibility = binding.tvAudioPartial.visibility
        scrollIfFollowing()
    }

    override fun onFinal(text: String) {
        if (text.isBlank()) return
        val id = captions.finalizePhrase(text)
        binding.tvAudioPartial.visibility = View.GONE
        binding.tvAudioPartialLabel.visibility = View.GONE
        renderCaptions()
        translations.submit(id, text)
    }

    private suspend fun translatePhrase(text: String): String? = withContext(Dispatchers.IO) {
        val romanized = KannadaRomanizer.romanize(text).trim()
        translationService.approvedCorrections.find(romanized, language)?.let { return@withContext it.correctedTranslation }
        if (language == SourceLanguage.KANGLISH) {
            translationService.ruleEngine.exactTranslation(romanized)?.let { return@withContext it }
        }
        val teacher = translationService.teacherService
        if (teacher.isTeacherEnabled && teacher.hasApiKey) {
            // One request per finalized segment, no serial native/romanized/review retries.
            teacher.translateDirect(text, language)
        } else if (language == SourceLanguage.KANGLISH) {
            translationService.translateMessage(ChatMessage("audio", "Voice", "", romanized), maxTokens = 96)
        } else null
    }

    private fun scrollIfFollowing() {
        val scroll = binding.audioTranscriptScroll
        val child = scroll.getChildAt(0) ?: return
        val distance = child.height - scroll.height - scroll.scrollY
        if (distance < (100 * resources.displayMetrics.density)) scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun renderCaptions() {
        val display = SpannableStringBuilder()
        val secondary = ContextCompat.getColor(this, R.color.text_secondary)
        captions.entries.forEachIndexed { index, entry ->
            if (index > 0) display.append("\n\n")
            display.append(entry.english.ifBlank { entry.kanglish })
            val detail = if (entry.english.isBlank()) entry.status else if (binding.switchAudioSource.isChecked) entry.kanglish else ""
            if (detail.isNotBlank()) {
                display.append("\n")
                val start = display.length
                display.append(detail)
                display.setSpan(ForegroundColorSpan(secondary), start, display.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                display.setSpan(RelativeSizeSpan(0.7f), start, display.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            }
        }
        val following = !binding.audioTranscriptScroll.canScrollVertically(1)
        binding.tvAudioTranscript.text = if (display.isEmpty()) getString(R.string.audio_empty) else display
        binding.btnAudioCopy.isEnabled = captions.finalized.isNotBlank()
        if (following) binding.audioTranscriptScroll.post { binding.audioTranscriptScroll.fullScroll(View.FOCUS_DOWN) }
    }
}
