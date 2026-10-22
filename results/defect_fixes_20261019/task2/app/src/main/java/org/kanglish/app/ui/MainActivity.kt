package org.kanglish.app.ui

import android.content.Intent
import android.content.ClipData
import android.content.ClipboardManager
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.widget.doAfterTextChanged
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.kanglish.app.R
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.data.FeedbackRepository
import org.kanglish.app.data.MessageStatus
import org.kanglish.app.data.WhatsAppParser
import org.kanglish.app.databinding.ActivityMainBinding
import org.kanglish.app.databinding.DialogFeedbackBinding
import org.kanglish.app.inference.TranslationService
import org.kanglish.app.overlay.FloatingSidebarService
import org.kanglish.app.overlay.KanglishAccessibilityService
import android.os.Build
import android.provider.Settings
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var translationService: TranslationService
    private lateinit var feedbackRepo: FeedbackRepository
    private lateinit var messageAdapter: MessageAdapter

    private val messages = mutableListOf<ChatMessage>()
    private val chatJobs = mutableListOf<Job>()
    private var batchJob: Job? = null
    private var quickJob: Job? = null
    private var quickRequest = 0
    private var quickResult = ""
    private var modelJob: Job? = null

    // SAF Document Pickers
    private val pickTextFileLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            importChatFromUri(uri)
        }
    }

    private val pickModelFileLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            loadGgufFromUri(uri)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { view, insets ->
            val edges = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            view.setPadding(edges.left, edges.top, edges.right, edges.bottom)
            insets
        }

        translationService = TranslationService(this)
        feedbackRepo = FeedbackRepository(this)

        setupRecyclerView()
        setupTabs()
        setupActions()
        setupTeacherAiSettings()
        setupSidebarExtensionUi()
        updateEngineStatusUi()
        refreshFeedbackList()
        checkAndAutoLoadModel()
        handleIncomingText(intent)
    }

    private fun setupRecyclerView() {
        messageAdapter = MessageAdapter(
            onTranslateClicked = { item, position ->
                translateSingleMessage(item, position)
            },
            onWrongMeaningClicked = { item, position ->
                showFeedbackDialog(item, position)
            },
            onTeachModelClicked = { item, position ->
                teachModel(item, position)
            }
        )
        binding.rvMessages.layoutManager = LinearLayoutManager(this)
        binding.rvMessages.adapter = messageAdapter
    }

    private fun setupTabs() {
        binding.tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab?) {
                showTab(when (tab?.position) {
                    1 -> binding.viewChatTab
                    2 -> binding.viewModelTab
                    else -> binding.viewImportTab
                })
            }
            override fun onTabUnselected(tab: TabLayout.Tab?) {}
            override fun onTabReselected(tab: TabLayout.Tab?) { onTabSelected(tab) }
        })
    }

    private fun showTab(activeView: View) {
        binding.viewChatTab.visibility = if (activeView == binding.viewChatTab) View.VISIBLE else View.GONE
        binding.viewImportTab.visibility = if (activeView == binding.viewImportTab) View.VISIBLE else View.GONE
        binding.viewModelTab.visibility = if (activeView == binding.viewModelTab) View.VISIBLE else View.GONE
        binding.viewFeedbackTab.visibility = if (activeView == binding.viewFeedbackTab) View.VISIBLE else View.GONE
    }

    private fun setupActions() {
        binding.btnParsePaste.setOnClickListener { translateQuickText() }
        binding.btnPasteClipboard.setOnClickListener {
            val clip = getSystemService(ClipboardManager::class.java).primaryClip
            val text = if (clip != null && clip.itemCount > 0) clip.getItemAt(0).text?.toString().orEmpty() else ""
            if (text.isBlank()) Toast.makeText(this, "Copy a text message first.", Toast.LENGTH_SHORT).show()
            else binding.etPasteInput.setText(text)
        }
        binding.etPasteInput.doAfterTextChanged {
            quickRequest++
            quickJob?.cancel()
            quickResult = ""
            binding.quickResultCard.visibility = View.GONE
        }
        binding.btnCopyQuick.setOnClickListener {
            if (quickResult.isNotBlank()) {
                getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Kanglish translation", quickResult))
                Toast.makeText(this, "Translation copied", Toast.LENGTH_SHORT).show()
            }
        }
        binding.btnClearPasteText.setOnClickListener { binding.etPasteInput.setText("") }
        binding.btnLoadSampleChat.setOnClickListener {
            assets.open("sample_chat.txt").bufferedReader().use { loadParsedText(it.readText()) }
        }
        binding.btnImportFile.setOnClickListener { pickTextFileLauncher.launch("text/*") }
        binding.btnClearChat.setOnClickListener { clearAll() }
        binding.btnQuickTranslateAll.setOnClickListener { translateAllMessages() }
        binding.btnPickModel.setOnClickListener { pickModelFileLauncher.launch(arrayOf("*/*")) }
        binding.btnUnloadModel.setOnClickListener {
            if (modelJob?.isActive == true) return@setOnClickListener
            modelJob = lifecycleScope.launch {
                setModelBusy(true)
                translationService.unloadModel()
                setModelBusy(false)
                updateEngineStatusUi()
            }
        }
        binding.btnAdvancedSettings.setOnClickListener {
            binding.cloudSettings.visibility = if (binding.cloudSettings.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }
        binding.btnOpenFeedback.setOnClickListener {
            refreshFeedbackList()
            showTab(binding.viewFeedbackTab)
        }
        binding.btnBackToSettings.setOnClickListener { showTab(binding.viewModelTab) }
        binding.btnClearFeedback.setOnClickListener {
            feedbackRepo.clearFeedback()
            refreshFeedbackList()
        }
    }

    private fun translateQuickText() {
        val text = binding.etPasteInput.text?.toString()?.trim().orEmpty()
        if (text.isBlank()) {
            binding.etPasteInput.error = "Enter or paste a message"
            return
        }
        quickJob?.cancel()
        val request = ++quickRequest
        quickResult = ""
        binding.quickResultCard.visibility = View.VISIBLE
        binding.pbQuickTranslating.visibility = View.VISIBLE
        binding.btnCopyQuick.isEnabled = false
        binding.tvQuickResult.text = "Translating on your phone..."
        quickJob = lifecycleScope.launch {
            try {
                quickResult = translationService.translateMessage(ChatMessage("quick", "You", "", text))
                binding.tvQuickResult.text = quickResult
                binding.btnCopyQuick.isEnabled = true
                updateEngineStatusUi()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                binding.tvQuickResult.text = e.message ?: "Translation failed. Try again."
            } finally {
                if (request == quickRequest) binding.pbQuickTranslating.visibility = View.GONE
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIncomingText(intent)
    }

    private fun handleIncomingText(source: Intent) {
        val text = source.getStringExtra(FloatingSidebarService.EXTRA_TEXT) ?: return
        source.removeExtra(FloatingSidebarService.EXTRA_TEXT)
        binding.tabLayout.getTabAt(0)?.select()
        binding.etPasteInput.setText(text)
        translateQuickText()
    }

    private fun cancelChatJobs() {
        batchJob?.cancel()
        chatJobs.forEach { it.cancel() }
        chatJobs.clear()
    }

    private fun loadParsedText(text: String) {
        val parsed = WhatsAppParser.parse(text)
        if (parsed.isEmpty()) {
            Toast.makeText(this, "No valid messages found in text", Toast.LENGTH_SHORT).show()
            return
        }

        cancelChatJobs()
        messages.clear()
        messages.addAll(parsed)
        messageAdapter.submitList(messages)

        binding.tvEmptyChat.visibility = View.GONE
        binding.rvMessages.visibility = View.VISIBLE

        // Switch to chat tab
        binding.tabLayout.getTabAt(1)?.select()
        Toast.makeText(this, "Loaded ${parsed.size} messages", Toast.LENGTH_SHORT).show()
    }

    private fun clearAll() {
        cancelChatJobs()
        messages.clear()
        messageAdapter.submitList(emptyList())
        binding.etPasteInput.setText("")
        binding.tvEmptyChat.visibility = View.VISIBLE
        binding.rvMessages.visibility = View.GONE
        Toast.makeText(this, "Cleared all messages and text", Toast.LENGTH_SHORT).show()
    }

    private fun importChatFromUri(uri: Uri) {
        lifecycleScope.launch {
            try {
                val content = withContext(Dispatchers.IO) {
                    contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
                        ?: throw IllegalArgumentException("Could not read this file")
                }
                loadParsedText(content)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { Toast.makeText(this@MainActivity, e.message, Toast.LENGTH_LONG).show() }
        }
    }

    private fun loadGgufFromUri(uri: Uri) {
        if (modelJob?.isActive == true) return
        modelJob = lifecycleScope.launch {
            setModelBusy(true)
            try {
                val success = translationService.importModel(uri)
                Toast.makeText(this@MainActivity, if (success) "Offline model ready" else "Could not load this GGUF. The previous model has been kept.", Toast.LENGTH_LONG).show()
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { Toast.makeText(this@MainActivity, e.message ?: "Model import failed", Toast.LENGTH_LONG).show() }
            finally {
                setModelBusy(false)
                updateEngineStatusUi()
            }
        }
    }

    private fun setModelBusy(busy: Boolean) {
        binding.btnPickModel.isEnabled = !busy
        binding.btnUnloadModel.isEnabled = !busy
        if (busy) binding.tvModelStatus.text = "Preparing model..."
    }

    private fun checkAndAutoLoadModel() {
        modelJob = lifecycleScope.launch {
            setModelBusy(true)
            try { translationService.ensureModelReady() }
            finally {
                setModelBusy(false)
                updateEngineStatusUi()
            }
        }
    }

    private fun setupTeacherAiSettings() {
        val teacher = translationService.teacherService
        binding.switchTeacherEnabled.isChecked = teacher.isTeacherEnabled
        binding.etGeminiKey.setText(teacher.geminiKey)
        binding.etGroqKey.setText(teacher.groqKey)
        updateTeacherStatusText()

        binding.switchTeacherEnabled.setOnCheckedChangeListener { _, isChecked ->
            teacher.isTeacherEnabled = isChecked
            updateTeacherStatusText()
            Toast.makeText(this, if (isChecked) "Cloud review enabled" else "Cloud review off", Toast.LENGTH_SHORT).show()
        }

        binding.btnSaveTeacherSettings.setOnClickListener {
            val gemini = binding.etGeminiKey.text?.toString()?.trim() ?: ""
            val groq = binding.etGroqKey.text?.toString()?.trim() ?: ""
            teacher.geminiKey = gemini
            teacher.groqKey = groq
            updateTeacherStatusText()
            Toast.makeText(this, "Teacher API settings saved!", Toast.LENGTH_SHORT).show()
        }
    }

    private fun updateTeacherStatusText() {
        val teacher = translationService.teacherService
        if (!teacher.isTeacherEnabled) {
            binding.tvTeacherStatus.text = "Cloud review off (Offline only)"
            binding.tvTeacherStatus.setTextColor(ContextCompat.getColor(this, R.color.text_muted))
        } else {
            val hasGemini = teacher.geminiKey.isNotBlank()
            val hasGroq = teacher.groqKey.isNotBlank()
            binding.tvTeacherStatus.text = when {
                hasGemini && hasGroq -> "Gemini + Groq fallback enabled"
                hasGemini -> "Gemini Flash Lite active"
                hasGroq -> "Groq fallback active"
                else -> "No API keys set (Teacher inactive)"
            }
            binding.tvTeacherStatus.setTextColor(
                ContextCompat.getColor(this, if (hasGemini || hasGroq) R.color.teacher_learn else R.color.status_pending)
            )
        }
    }

    private var isUpdatingOverlaySwitch = false

    private fun setupSidebarExtensionUi() {
        binding.switchFloatingSidebar.setOnCheckedChangeListener { _, isChecked ->
            if (isUpdatingOverlaySwitch) return@setOnCheckedChangeListener
            if (isChecked) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                    isUpdatingOverlaySwitch = true
                    binding.switchFloatingSidebar.isChecked = false
                    isUpdatingOverlaySwitch = false
                    binding.switchFloatingSidebar.tag = "requested"
                    val intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName")
                    )
                    startActivity(intent)
                    Toast.makeText(
                        this,
                        "Please allow 'Display over other apps' to enable the sidebar extension",
                        Toast.LENGTH_LONG
                    ).show()
                } else {
                    FloatingSidebarService.start(this)
                    binding.tvSidebarStatus.text = "Sidebar active! Floating badge is on your screen."
                    Toast.makeText(this, "Sidebar extension active! Tap the floating badge on your screen 🌐", Toast.LENGTH_SHORT).show()
                }
            } else {
                FloatingSidebarService.stop(this)
                binding.tvSidebarStatus.text = "Copy a WhatsApp message, then tap the bubble."
            }
        }

        binding.btnEnableAccessibility.setOnClickListener {
            if (KanglishAccessibilityService.isEnabled(this)) {
                Toast.makeText(this, "Hold-to-Translate is active! Hold any message in WhatsApp to translate.", Toast.LENGTH_SHORT).show()
            } else {
                AlertDialog.Builder(this, R.style.Theme_Kanglish)
                    .setTitle("Enable Hold-to-Translate")
                    .setMessage(
                        "1. Tap 'Open Settings' below.\n" +
                        "2. Tap 'Installed apps' -> 'Kanglish Translator' -> Turn ON.\n\n" +
                        "⚠️ If Android says 'Restricted setting':\n" +
                        "Go to Phone Settings -> Apps -> Kanglish Translator -> tap the 3 dots (⋮) top right -> 'Allow restricted settings'."
                    )
                    .setPositiveButton("Open Settings") { _, _ ->
                        KanglishAccessibilityService.openSettings(this)
                    }
                    .setNegativeButton("Cancel", null)
                    .show()
            }
        }

        // Test Sidebar Button (Immediate visual demonstration)
        binding.btnTestSidebar.setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                binding.switchFloatingSidebar.tag = "requested"
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
                Toast.makeText(
                    this,
                    "First allow 'Display over other apps' to show the floating sidebar",
                    Toast.LENGTH_LONG
                ).show()
            } else {
                FloatingSidebarService.start(this)
                updateSidebarStatusIndicators()
                Toast.makeText(this, "Bubble ready. Copy a message, then tap it.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && Settings.canDrawOverlays(this) && binding.switchFloatingSidebar.tag == "requested") {
            binding.switchFloatingSidebar.tag = null
            FloatingSidebarService.start(this)
        }
        updateSidebarStatusIndicators()
    }

    private fun updateSidebarStatusIndicators() {
        val overlayRunning = FloatingSidebarService.isRunning
        isUpdatingOverlaySwitch = true
        binding.switchFloatingSidebar.isChecked = overlayRunning
        isUpdatingOverlaySwitch = false

        if (overlayRunning) {
            binding.tvSidebarStatus.text = "Sidebar active! Floating badge is on your screen."
        } else {
            binding.tvSidebarStatus.text = "Copy a WhatsApp message, then tap the bubble."
        }

        val a11yActive = KanglishAccessibilityService.isEnabled(this)
        if (a11yActive) {
            binding.tvAccessibilityIndicator.text = "Hold detection: Active"
            binding.tvAccessibilityIndicator.setTextColor(ContextCompat.getColor(this, R.color.teacher_learn))
            binding.btnEnableAccessibility.text = "Hold-to-Translate Active"
        } else {
            binding.tvAccessibilityIndicator.text = "Hold detection: Off"
            binding.tvAccessibilityIndicator.setTextColor(ContextCompat.getColor(this, R.color.text_muted))
            binding.btnEnableAccessibility.text = "Enable Hold-to-Translate"
        }
    }

    private fun teachModel(item: ChatMessage, position: Int) {
        if (!item.isTeacherChecked || item.isTeacherMatch || item.isTeacherUncertain) return
        val suggestedMeaning = item.teacherSuggestion
        if (suggestedMeaning.isBlank()) return

        // Permanently learn the term in local glossary
        translationService.teachModel(item.originalText, suggestedMeaning)
        item.isLearned = true

        // Log into feedback repository
        feedbackRepo.saveFeedback(
            sender = item.sender,
            originalText = item.originalText,
            generatedTranslation = item.translatedText,
            userCorrection = "Teacher Learned: $suggestedMeaning"
        )

        messageAdapter.updateItem(position)
        refreshFeedbackList()
        Toast.makeText(this, "Learned! Saved to local glossary.", Toast.LENGTH_SHORT).show()
    }

    private fun translateSingleMessage(item: ChatMessage, position: Int) {
        if (item.status == MessageStatus.TRANSLATING) return
        chatJobs.removeAll { it.isCompleted }
        chatJobs += lifecycleScope.launch { translateOne(item, messages.take(position)) }
    }

    private suspend fun translateOne(item: ChatMessage, history: List<ChatMessage>) {
        if (item.status == MessageStatus.TRANSLATING) return
        item.status = MessageStatus.TRANSLATING
        item.isTeacherChecked = false
        item.isTeacherUncertain = false
        item.teacherSuggestion = ""
        item.teacherExplanation = ""
        item.isLearned = false
        messageAdapter.updateItem(messages.indexOf(item))
        try {
            item.translatedText = translationService.translateMessage(item, history)
            item.status = MessageStatus.TRANSLATED
            messageAdapter.updateItem(messages.indexOf(item))
            if (translationService.teacherService.isTeacherEnabled) {
                chatJobs += lifecycleScope.launch {
                    translationService.verifyWithTeacher(item)
                    messageAdapter.updateItem(messages.indexOf(item))
                }
            }
        } catch (e: CancellationException) {
            item.status = MessageStatus.PENDING
            messageAdapter.updateItem(messages.indexOf(item))
            throw e
        } catch (e: Exception) {
            item.status = MessageStatus.FAILED
            messageAdapter.updateItem(messages.indexOf(item))
        }
    }

    private fun translateAllMessages() {
        if (batchJob?.isActive == true || messages.isEmpty()) return
        binding.tabLayout.getTabAt(1)?.select()
        val snapshot = messages.toList()
        batchJob = lifecycleScope.launch {
            binding.btnQuickTranslateAll.isEnabled = false
            try {
                snapshot.forEachIndexed { index, item ->
                    if (item.status != MessageStatus.TRANSLATED) translateOne(item, snapshot.take(index))
                }
            } finally { binding.btnQuickTranslateAll.isEnabled = true }
        }
    }

    private fun showFeedbackDialog(item: ChatMessage, position: Int) {
        val dialogBinding = DialogFeedbackBinding.inflate(LayoutInflater.from(this))
        dialogBinding.dialogTvOriginal.text = "Original (${item.sender}): ${item.originalText}"
        dialogBinding.dialogTvCurrentTranslation.text = "Generated: ${item.translatedText.ifEmpty { "(none)" }}"

        AlertDialog.Builder(this, R.style.Theme_Kanglish)
            .setView(dialogBinding.root)
            .setPositiveButton(R.string.btn_save_feedback) { _, _ ->
                val correction = dialogBinding.etCorrection.text?.toString()?.trim() ?: ""
                if (correction.isNotBlank()) {
                    item.isFlaggedWrong = true
                    item.userCorrection = correction
                    feedbackRepo.saveFeedback(
                        sender = item.sender,
                        originalText = item.originalText,
                        generatedTranslation = item.translatedText,
                        userCorrection = correction
                    )
                    messageAdapter.updateItem(position)
                    Toast.makeText(this, "Feedback saved locally", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton(R.string.btn_cancel, null)
            .show()
    }

    private fun updateEngineStatusUi() {
        val loaded = translationService.isLlamaLoaded()
        binding.tvEngineStatusHeader.text = if (loaded) "On-device model ready" else "Glossary ready"
        binding.tvModelStatus.text = if (loaded) "Model loaded" else "No model loaded"
        binding.btnUnloadModel.isEnabled = loaded && binding.btnPickModel.isEnabled
        binding.tvModelDetails.text = if (loaded) {
            "Your GGUF runs on this phone. Exact saved phrases use the glossary first."
        } else {
            "Choose your Kanglish Qwen2.5 0.5B GGUF for full sentences. Glossary matches work without it."
        }
    }

    private fun refreshFeedbackList() {
        val feedbackList = feedbackRepo.getAllFeedback()
        if (feedbackList.isEmpty()) {
            binding.tvFeedbackEmpty.visibility = View.VISIBLE
            binding.tvFeedbackList.visibility = View.GONE
        } else {
            binding.tvFeedbackEmpty.visibility = View.GONE
            val sb = StringBuilder()
            feedbackList.forEachIndexed { idx, f ->
                sb.append("${idx + 1}. [${f.timestamp}] ${f.sender}\n")
                sb.append("Original: ${f.originalText}\n")
                sb.append("Generated: ${f.generatedTranslation}\n")
                sb.append("Nuance / Correction: ${f.userCorrection}\n\n")
            }
            binding.tvFeedbackList.text = sb.toString()
            binding.tvFeedbackList.visibility = View.VISIBLE
        }
    }
}
