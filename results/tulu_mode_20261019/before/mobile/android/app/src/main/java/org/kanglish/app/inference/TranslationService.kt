package org.kanglish.app.inference

import android.content.Context
import android.net.Uri
import android.system.Os
import android.util.Log
import org.kanglish.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.data.ApprovedCorrectionRepository
import org.kanglish.app.data.GlossaryManager
import java.io.File
import kotlin.coroutines.coroutineContext

class TranslationService(context: Context, val teacherService: TeacherService = TeacherService(context)) {
    private val context = context.applicationContext
    val glossaryManager = GlossaryManager.shared(this.context)
    val approvedCorrections = ApprovedCorrectionRepository(this.context)
    private val ruleEngine = GlossaryRuleEngine(glossaryManager)
    private val modelFile get() = File(context.filesDir, "active_model.gguf")
    private val modelPrefs get() = context.getSharedPreferences("model_prefs", Context.MODE_PRIVATE)

    companion object {
        // One JNI model/context is shared by the activity and overlay.
        private val engineMutex = Mutex()
        private var attemptedAutoLoad = false
    }

    fun teachModel(kanglish: String, englishCorrection: String) {
        glossaryManager.addLearnedTerm(kanglish, englishCorrection)
    }

    fun approveTeacherTranslation(message: ChatMessage) {
        require(message.isTeacherChecked && !message.isTeacherUncertain && message.teacherSuggestion.isNotBlank()) {
            "Only a completed teacher translation can be approved."
        }
        approvedCorrections.save(message.originalText, message.translatedText, message.teacherSuggestion, message.teacherExplanation)
    }

    suspend fun verifyWithTeacher(message: ChatMessage): TeacherResult {
        val studentText = message.translatedText
        val result = teacherService.verifyTranslation(message.originalText, studentText)
        if (result.success && message.translatedText == studentText) {
            message.isTeacherChecked = true
            message.isTeacherMatch = result.isMatch
            message.teacherSuggestion = result.teacherTranslation
            message.isTeacherUncertain = result.isUncertain
            message.teacherExplanation = result.explanation
        }
        return result
    }

    fun isLlamaLoaded(): Boolean = LlamaNativeBridge.isModelLoaded()

    private fun loadStoredModel(): Boolean {
        if (isLlamaLoaded()) return true
        if (attemptedAutoLoad || !modelPrefs.getBoolean("load_on_start", true)) return false
        attemptedAutoLoad = true
        return modelFile.isFile && LlamaNativeBridge.initialize(context) && LlamaNativeBridge.loadModel(modelFile.absolutePath)
    }

    suspend fun ensureModelReady(): Boolean = withContext(Dispatchers.IO) {
        engineMutex.withLock { loadStoredModel() }
    }

    suspend fun unloadModel() = withContext(Dispatchers.IO) {
        engineMutex.withLock {
            modelPrefs.edit().putBoolean("load_on_start", false).apply()
            attemptedAutoLoad = true
            LlamaNativeBridge.unloadModel()
        }
    }

    suspend fun importModel(uri: Uri): Boolean = withContext(Dispatchers.IO) {
        engineMutex.withLock {
            val candidate = File(context.filesDir, "importing_model.gguf")
            val hadModel = isLlamaLoaded()
            var replacedModel = false
            try {
                val input = context.contentResolver.openInputStream(uri)
                    ?: throw IllegalArgumentException("Could not open this model file")
                input.use { source -> candidate.outputStream().use { source.copyTo(it) } }
                val magic = candidate.inputStream().use { inputStream ->
                    val bytes = ByteArray(4)
                    if (inputStream.read(bytes) == 4) String(bytes, Charsets.US_ASCII) else ""
                }
                require(magic == "GGUF") { "Choose a GGUF model file." }
                coroutineContext.ensureActive()
                if (!LlamaNativeBridge.initialize(context)) throw IllegalStateException("The native engine is unavailable on this device.")
                replacedModel = true
                if (!LlamaNativeBridge.loadModel(candidate.absolutePath)) return@withLock false
                // Rename after validation. Never overwrite a file that the current model maps.
                Os.rename(candidate.absolutePath, modelFile.absolutePath)
                replacedModel = false
                attemptedAutoLoad = true
                modelPrefs.edit().putBoolean("load_on_start", true).apply()
                true
            } finally {
                if (replacedModel) {
                    LlamaNativeBridge.unloadModel()
                    if (hadModel && modelFile.isFile) LlamaNativeBridge.loadModel(modelFile.absolutePath)
                }
                candidate.delete()
            }
        }
    }

    suspend fun translateMessage(message: ChatMessage, contextHistory: List<ChatMessage> = emptyList()): String = withContext(Dispatchers.Default) {
        val text = message.originalText.trim()
        require(text.isNotEmpty()) { "Enter or paste a message." }
        require(text.length <= 4000) { "Translate a shorter message (up to 4,000 characters)." }
        message.usedApprovedCorrection = false
        approvedCorrections.find(text)?.let {
            message.usedApprovedCorrection = true
            return@withContext it.correctedTranslation
        }
        ruleEngine.exactTranslation(text)?.let { return@withContext it }
        message.matchedGlossaryTerms = glossaryManager.findMatches(text)
        engineMutex.withLock {
            coroutineContext.ensureActive()
            if (!loadStoredModel()) {
                throw IllegalStateException("Load your Kanglish 0.5B GGUF in Settings to translate full sentences. Saved glossary phrases work without a model.")
            }
            val hints = TranslationPrompt.selectHints(text, message.matchedGlossaryTerms)
            val prompt = TranslationPrompt.build(text, contextHistory, hints)
            // Requested diagnostics only: never log arbitrary private messages or release prompts.
            if (BuildConfig.DEBUG && text in setOf("naale college ge barthira?", "yenu guru ivattu plan?")) {
                Log.d("KanglishPrompt", "input=$text; final_hints=$hints")
                prompt.chunked(2000).forEachIndexed { index, chunk ->
                    Log.d("KanglishPrompt", "final_prompt[$index]=$chunk")
                }
            }
            val raw = LlamaNativeBridge.translate(prompt, maxTokens = 192)
            if (raw.startsWith("[Error:")) throw IllegalStateException(raw.removePrefix("[Error: ").removeSuffix("]"))
            val clean = TranslationPrompt.clean(raw)
            if (clean.isBlank()) throw IllegalStateException("The model returned no translation. Try a shorter message.")
            clean
        }
    }
}
