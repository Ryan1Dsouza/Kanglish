package org.kanglish.app.overlay

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.kanglish.app.R
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.data.FeedbackRepository
import org.kanglish.app.inference.TranslationService
import org.kanglish.app.ui.MainActivity

class FloatingSidebarService : Service() {

    companion object {
        const val ACTION_TRANSLATE = "org.kanglish.app.ACTION_TRANSLATE"
        const val EXTRA_TEXT = "extra_text"
        private const val CHANNEL_ID = "kanglish_sidebar_channel"
        private const val NOTIFICATION_ID = 1001

        var isRunning = false
            private set

        fun start(context: Context) {
            if (!Settings.canDrawOverlays(context)) return
            val intent = Intent(context, FloatingSidebarService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                Toast.makeText(context, "Open Kanglish to start the floating bubble.", Toast.LENGTH_LONG).show()
            }
        }

        fun stop(context: Context) {
            isRunning = false
            try {
                context.stopService(Intent(context, FloatingSidebarService::class.java))
            } catch (_: Exception) {}
        }

        fun translateAndShow(context: Context, text: String) {
            if (text.isBlank()) return
            if (!Settings.canDrawOverlays(context)) {
                context.startActivity(Intent(context, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    putExtra(EXTRA_TEXT, text)
                })
                return
            }
            val intent = Intent(context, FloatingSidebarService::class.java).apply {
                action = ACTION_TRANSLATE
                putExtra(EXTRA_TEXT, text)
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                context.startActivity(Intent(context, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    putExtra(EXTRA_TEXT, text)
                })
            }
        }
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private lateinit var windowParams: WindowManager.LayoutParams

    private lateinit var translationService: TranslationService
    private lateinit var feedbackRepo: FeedbackRepository

    private lateinit var pillHandle: View
    private lateinit var panelExpanded: View
    private lateinit var tvFloatingOriginal: TextView
    private lateinit var tvFloatingTranslated: TextView
    private lateinit var pbFloatingTranslating: ProgressBar
    private lateinit var btnFloatingCopy: TextView
    private lateinit var boxFloatingTeacher: View
    private lateinit var tvFloatingTeacherBadge: TextView
    private lateinit var tvFloatingTeacherText: TextView
    private lateinit var btnFloatingTeach: TextView

    private var currentKanglishText: String = ""
    private var currentTranslatedText: String = ""
    private var currentTeacherSuggestion: String = ""
    private var translationJob: Job? = null
    private var requestId = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        translationService = TranslationService(this)
        feedbackRepo = FeedbackRepository(this)

        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(
                    NOTIFICATION_ID,
                    buildNotification(),
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
                )
            } else {
                startForeground(NOTIFICATION_ID, buildNotification())
            }
        } catch (e: Exception) {
            stopSelf()
            return
        }

        if (!Settings.canDrawOverlays(this)) {
            stopSelf()
            return
        }
        initWindowManager()
        Toast.makeText(this, "Kanglish Sidebar active! Tap the floating badge on your screen 🌐", Toast.LENGTH_LONG).show()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (::floatingView.isInitialized && floatingView.isAttachedToWindow && action == ACTION_TRANSLATE) {
            val text = intent.getStringExtra(EXTRA_TEXT) ?: ""
            if (text.isNotBlank()) {
                expandPanel()
                runTranslation(text)
            }
        }
        return START_NOT_STICKY
    }

    private fun dpToPx(dp: Int): Int =
        (dp * resources.displayMetrics.density).toInt()

    private fun initWindowManager() {
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val themedContext = androidx.appcompat.view.ContextThemeWrapper(this, R.style.Theme_Kanglish)
        val inflater = LayoutInflater.from(themedContext)
        floatingView = inflater.inflate(R.layout.layout_floating_sidebar, null)

        val layoutFlag = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        windowParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutFlag,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (resources.displayMetrics.widthPixels - dpToPx(70)).coerceAtLeast(0)
            y = (resources.displayMetrics.heightPixels / 2) - dpToPx(40)
        }

        bindViews()
        setupTouchHandlers()

        try {
            windowManager.addView(floatingView, windowParams)
            isRunning = true
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(this, "Permission required: Enable 'Display over other apps'", Toast.LENGTH_LONG).show()
            stopSelf()
        }
    }

    private fun bindViews() {
        pillHandle = floatingView.findViewById(R.id.pillHandle)
        panelExpanded = floatingView.findViewById(R.id.panelExpanded)
        tvFloatingOriginal = floatingView.findViewById(R.id.tvFloatingOriginal)
        tvFloatingTranslated = floatingView.findViewById(R.id.tvFloatingTranslated)
        pbFloatingTranslating = floatingView.findViewById(R.id.pbFloatingTranslating)
        btnFloatingCopy = floatingView.findViewById(R.id.btnFloatingCopy)
        boxFloatingTeacher = floatingView.findViewById(R.id.boxFloatingTeacher)
        tvFloatingTeacherBadge = floatingView.findViewById(R.id.tvFloatingTeacherBadge)
        tvFloatingTeacherText = floatingView.findViewById(R.id.tvFloatingTeacherText)
        btnFloatingTeach = floatingView.findViewById(R.id.btnFloatingTeach)

        panelExpanded.layoutParams.width = minOf(dpToPx(344), resources.displayMetrics.widthPixels - dpToPx(24))
        floatingView.findViewById<View>(R.id.panelScroll).layoutParams.height = minOf(dpToPx(280), resources.displayMetrics.heightPixels / 3)
        btnFloatingCopy.isEnabled = false

        // Quick Paste & Translate from WhatsApp button
        floatingView.findViewById<View>(R.id.btnFloatingPaste).setOnClickListener {
            triggerClipboardPaste()
        }

        // Minimize
        floatingView.findViewById<View>(R.id.btnMinimize).setOnClickListener {
            collapsePanel()
        }

        // Close service
        floatingView.findViewById<View>(R.id.btnCloseOverlay).setOnClickListener {
            stopSelf()
        }

        // Open App
        floatingView.findViewById<View>(R.id.btnFloatingOpenApp).setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
            collapsePanel()
        }

        // Clear
        floatingView.findViewById<View>(R.id.btnFloatingClear).setOnClickListener {
            translationJob?.cancel()
            requestId++
            pbFloatingTranslating.visibility = View.GONE
            btnFloatingCopy.isEnabled = false
            currentKanglishText = ""
            currentTranslatedText = ""
            currentTeacherSuggestion = ""
            tvFloatingOriginal.text = "Copy a message in WhatsApp, then tap Paste copied text."
            tvFloatingTranslated.text = "Translation ready"
            boxFloatingTeacher.visibility = View.GONE
        }

        // Copy translation
        btnFloatingCopy.setOnClickListener {
            if (currentTranslatedText.isNotBlank()) {
                val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = ClipData.newPlainText("Kanglish Translation", currentTranslatedText)
                clipboard.setPrimaryClip(clip)
                Toast.makeText(this, "Copied to clipboard!", Toast.LENGTH_SHORT).show()
            }
        }

        // Save meaning
        btnFloatingTeach.setOnClickListener {
            if (currentKanglishText.isNotBlank() && currentTeacherSuggestion.isNotBlank()) {
                translationService.teachModel(currentKanglishText, currentTeacherSuggestion)
                feedbackRepo.saveFeedback(
                    sender = "Screen Overlay",
                    originalText = currentKanglishText,
                    generatedTranslation = currentTranslatedText,
                    userCorrection = "Teacher Learned: $currentTeacherSuggestion"
                )
                btnFloatingTeach.text = "✓ Learned"
                btnFloatingTeach.isEnabled = false
                Toast.makeText(this, "Permanently saved to local offline glossary!", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun setupTouchHandlers() {
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f
        var isClick = true

        pillHandle.setOnClickListener { triggerClipboardPaste() }
        pillHandle.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = windowParams.x
                    initialY = windowParams.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    isClick = true
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val deltaX = (event.rawX - initialTouchX).toInt()
                    val deltaY = (event.rawY - initialTouchY).toInt()
                    if (Math.abs(deltaX) > 8 || Math.abs(deltaY) > 8) {
                        isClick = false
                    }
                    windowParams.x = (initialX + deltaX).coerceIn(0, (resources.displayMetrics.widthPixels - dpToPx(56)).coerceAtLeast(0))
                    windowParams.y = (initialY + deltaY).coerceIn(0, (resources.displayMetrics.heightPixels - dpToPx(104)).coerceAtLeast(0))
                    try {
                        windowManager.updateViewLayout(floatingView, windowParams)
                    } catch (_: Exception) {}
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (isClick) {
                        pillHandle.performClick()
                    }
                    true
                }
                else -> false
            }
        }

        val panelHeader = floatingView.findViewById<View>(R.id.panelHeader)
        var panelInitialX = 0
        var panelInitialY = 0
        var panelTouchX = 0f
        var panelTouchY = 0f

        panelHeader?.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    panelInitialX = windowParams.x
                    panelInitialY = windowParams.y
                    panelTouchX = event.rawX
                    panelTouchY = event.rawY
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val deltaX = (event.rawX - panelTouchX).toInt()
                    val deltaY = (event.rawY - panelTouchY).toInt()
                    windowParams.x = (panelInitialX + deltaX).coerceIn(0, (resources.displayMetrics.widthPixels - panelExpanded.width).coerceAtLeast(0))
                    windowParams.y = (panelInitialY + deltaY).coerceIn(0, (resources.displayMetrics.heightPixels - panelExpanded.height - dpToPx(48)).coerceAtLeast(0))
                    try {
                        windowManager.updateViewLayout(floatingView, windowParams)
                    } catch (_: Exception) {}
                    true
                }
                else -> false
            }
        }
    }

    private fun expandPanel() {
        pillHandle.visibility = View.GONE
        panelExpanded.visibility = View.VISIBLE
        val screenWidth = resources.displayMetrics.widthPixels
        val screenHeight = resources.displayMetrics.heightPixels
        windowParams.x = (screenWidth - panelExpanded.layoutParams.width - dpToPx(12)).coerceAtLeast(0)
        val panelHeight = floatingView.findViewById<View>(R.id.panelScroll).layoutParams.height + dpToPx(216)
        windowParams.y = windowParams.y.coerceIn(0, (screenHeight - panelHeight - dpToPx(48)).coerceAtLeast(0))
        try {
            windowManager.updateViewLayout(floatingView, windowParams)
        } catch (_: Exception) {}
    }

    private fun collapsePanel() {
        panelExpanded.visibility = View.GONE
        pillHandle.visibility = View.VISIBLE
        val screenWidth = resources.displayMetrics.widthPixels
        windowParams.x = (screenWidth - dpToPx(70)).coerceAtLeast(0)
        try {
            windowManager.updateViewLayout(floatingView, windowParams)
        } catch (_: Exception) {}
    }

    private fun triggerClipboardPaste() {
        collapsePanel()
        try {
            Log.d("KanglishClipboard", "bubble requested focused clipboard capture")
            startActivity(ClipboardTrampolineActivity.captureIntent(this))
        } catch (e: RuntimeException) {
            Log.w("KanglishClipboard", "capture launch failed: ${e.javaClass.simpleName}")
            Toast.makeText(this, "Use Paste copied text in the Kanglish notification, or open the app and tap Paste.", Toast.LENGTH_LONG).show()
        }
    }

    fun runTranslation(kanglishText: String) {
        translationJob?.cancel()
        val activeRequest = ++requestId
        currentTranslatedText = ""
        currentTeacherSuggestion = ""
        btnFloatingCopy.isEnabled = false
        expandPanel()
        currentKanglishText = kanglishText
        tvFloatingOriginal.text = kanglishText
        tvFloatingTranslated.text = "Translating with on-device model..."
        pbFloatingTranslating.visibility = View.VISIBLE
        boxFloatingTeacher.visibility = View.GONE

        translationJob = serviceScope.launch {
            try {
                val msg = ChatMessage(id = "overlay", sender = "Screen", timestamp = "", originalText = kanglishText)
                val translation = translationService.translateMessage(msg)
                msg.translatedText = translation
                currentTranslatedText = translation
                btnFloatingCopy.isEnabled = true

                tvFloatingTranslated.text = translation
                pbFloatingTranslating.visibility = View.GONE

                // Async Teacher Check if online & enabled
                if (translationService.teacherService.isTeacherEnabled) {
                    val teacherRes = withContext(Dispatchers.IO) {
                        translationService.verifyWithTeacher(msg)
                    }
                    if (teacherRes.success) {
                        boxFloatingTeacher.visibility = View.VISIBLE
                        if (teacherRes.isUncertain) {
                            tvFloatingTeacherBadge.text = "UNCERTAIN"
                            tvFloatingTeacherBadge.setTextColor(ContextCompat.getColor(this@FloatingSidebarService, R.color.teacher_badge))
                            tvFloatingTeacherText.text = teacherRes.explanation
                            currentTeacherSuggestion = ""
                            btnFloatingTeach.visibility = View.GONE
                        } else if (teacherRes.isMatch) {
                            tvFloatingTeacherBadge.text = "🎓 CLOUD REVIEW"
                            tvFloatingTeacherBadge.setTextColor(ContextCompat.getColor(this@FloatingSidebarService, R.color.teacher_learn))
                            tvFloatingTeacherText.text = "The reviewer agrees with this translation."
                            btnFloatingTeach.visibility = View.GONE
                        } else {
                            tvFloatingTeacherBadge.text = "💡 TEACHER AI SUGGESTION"
                            tvFloatingTeacherBadge.setTextColor(ContextCompat.getColor(this@FloatingSidebarService, R.color.teacher_badge))
                            tvFloatingTeacherText.text = teacherRes.teacherTranslation
                            currentTeacherSuggestion = teacherRes.teacherTranslation
                            btnFloatingTeach.visibility = View.VISIBLE
                            btnFloatingTeach.text = "Save meaning"
                            btnFloatingTeach.isEnabled = true
                        }
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                tvFloatingTranslated.text = e.message ?: "Translation failed. Try again."
            } finally {
                if (activeRequest == requestId) pbFloatingTranslating.visibility = View.GONE
            }
        }
    }

    private fun buildNotification(): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Kanglish Sidebar Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Kanglish floating sidebar active over chat apps"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Kanglish Floating Sidebar Active")
            .setContentText("Copy a message, then tap the Kanglish bubble")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .addAction(android.R.drawable.ic_menu_edit, "Paste copied text", PendingIntent.getActivity(
                this, 1, ClipboardTrampolineActivity.captureIntent(this),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
            ))
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        serviceScope.cancel()
        if (::floatingView.isInitialized && floatingView.isAttachedToWindow) {
            try {
                windowManager.removeView(floatingView)
            } catch (_: Exception) {}
        }
    }
}
