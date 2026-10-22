package org.kanglish.app

import android.content.ClipboardManager
import android.os.Looper
import android.view.View
import android.widget.EditText
import android.widget.TextView
import com.google.android.material.switchmaterial.SwitchMaterial
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.inference.TeacherService
import org.kanglish.app.data.ApprovedCorrectionRepository
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.data.SourceLanguage
import kotlinx.coroutines.runBlocking
import org.kanglish.app.inference.TranslationService
import org.kanglish.app.ui.MainActivity
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class QuickTeacherReviewTest {
    private data class Reply(
        val review: String = "",
        val code: Int = 200,
        val release: CountDownLatch = CountDownLatch(0),
        val started: CountDownLatch = CountDownLatch(1),
        val finished: CountDownLatch = CountDownLatch(1)
    )
    private data class Request(val url: URL, val body: String)

    private val replies = ConcurrentLinkedQueue<Reply>()
    private val allReplies = mutableListOf<Reply>()
    private val requests = ConcurrentLinkedQueue<Request>()
    private lateinit var controller: ActivityController<MainActivity>
    private lateinit var activity: MainActivity
    private lateinit var teacher: TeacherService

    @Before fun setUp() {
        val app = RuntimeEnvironment.getApplication()
        teacher = TeacherService(app) { url ->
            val reply = replies.poll() ?: throw IOException("Unexpected fixture request")
            object : HttpURLConnection(url) {
                private val output = ByteArrayOutputStream()
                override fun connect() {}
                override fun usingProxy() = false
                override fun disconnect() { reply.finished.countDown() }
                override fun getOutputStream() = output
                override fun getResponseCode(): Int {
                    requests.add(Request(url, output.toString("UTF-8")))
                    reply.started.countDown()
                    if (!reply.release.await(5, TimeUnit.SECONDS)) throw IOException("Fixture response was not released")
                    return reply.code
                }
                override fun getInputStream() = envelope(url, reply.review).byteInputStream()
            }
        }
        teacher.geminiKey = "GEMINI_KEY_FIXTURE"
        teacher.isTeacherEnabled = true
        controller = Robolectric.buildActivity(MainActivity::class.java).setup()
        activity = controller.get()
        val service = TranslationService(app, teacher)
        service.teachModel("source fixture", "STUDENT_FIXTURE")
        service.teachModel("second source fixture", "SECOND_STUDENT_FIXTURE")
        MainActivity::class.java.getDeclaredField("translationService").apply { isAccessible = true }
            .set(activity, service)
    }

    @After fun tearDown() {
        allReplies.forEach { it.release.countDown() }
        if (::controller.isInitialized) controller.pause().stop().destroy()
        shadowOf(Looper.getMainLooper()).idle()
    }

    @Test fun showsTheTeachersOwnTranslationEvenWhenItAgreesAndCopiesEachAnswerSeparately() {
        val reply = enqueue(review("match", "TEACHER_FIXTURE"), blocked = true)
        translate()
        waitFor { reply.started.count == 0L }
        assertEquals("STUDENT_FIXTURE", text(R.id.tvQuickResult))
        assertEquals(View.GONE, view(R.id.pbQuickTranslating).visibility)
        assertEquals(View.VISIBLE, view(R.id.pbQuickTeacher).visibility)
        assertEquals(activity.getString(R.string.quick_teacher_loading), text(R.id.tvQuickTeacherStatus))
        val prompt = JSONObject(requests.single().body).getJSONArray("contents").getJSONObject(0)
            .getJSONArray("parts").getJSONObject(0).getString("text")
        val input = JSONObject(prompt.substringAfter("Input JSON:").trim())
        assertEquals("source fixture", input.getString("originalKanglish"))
        assertEquals("STUDENT_FIXTURE", input.getString("studentEnglish"))
        assertNull(requests.single().url.query)
        reply.release.countDown()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "TEACHER_FIXTURE" }
        assertEquals(activity.getString(R.string.quick_teacher_match), text(R.id.tvQuickTeacherStatus))
        assertEquals(View.VISIBLE, view(R.id.tvQuickTeacherTranslation).visibility)
        val clipboard = activity.getSystemService(ClipboardManager::class.java)
        view(R.id.btnCopyQuickTeacher).performClick()
        assertEquals("TEACHER_FIXTURE", clipboard.primaryClip!!.getItemAt(0).text.toString())
        view(R.id.btnCopyQuick).performClick()
        assertEquals("STUDENT_FIXTURE", clipboard.primaryClip!!.getItemAt(0).text.toString())
    }

    @Test fun correctionShowsBothTheTeacherTranslationAndItsReason() {
        enqueue(review("mismatch", "CORRECTION_FIXTURE", "REASON_FIXTURE"))
        translate()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "CORRECTION_FIXTURE" }
        assertEquals("STUDENT_FIXTURE", text(R.id.tvQuickResult))
        assertEquals(activity.getString(R.string.quick_teacher_mismatch), text(R.id.tvQuickTeacherStatus))
        assertEquals("REASON_FIXTURE", text(R.id.tvQuickTeacherExplanation))
        assertEquals(View.VISIBLE, view(R.id.btnCopyQuickTeacher).visibility)
    }

    @Test fun uncertaintyShowsItsReasonWithoutOfferingAGuessedTranslation() {
        enqueue(review("uncertain", "", "CONTEXT_REQUIRED_FIXTURE"))
        translate()
        waitFor { text(R.id.tvQuickTeacherStatus) == activity.getString(R.string.quick_teacher_uncertain) }
        assertEquals("CONTEXT_REQUIRED_FIXTURE", text(R.id.tvQuickTeacherExplanation))
        assertEquals(View.GONE, view(R.id.tvQuickTeacherTranslation).visibility)
        assertEquals(View.GONE, view(R.id.btnCopyQuickTeacher).visibility)
        assertEquals(View.GONE, view(R.id.btnApproveQuickTeacher).visibility)
        view(R.id.btnApproveQuickTeacher).performClick()
        assertTrue(ApprovedCorrectionRepository(activity).getAll().isEmpty())
        assertEquals("STUDENT_FIXTURE", text(R.id.tvQuickResult))
    }

    @Test fun approvingACorrectionPersistsItForFutureOfflineTranslationsAndTraining() {
        enqueue(review("mismatch", "APPROVED_FIXTURE", "REASON_FIXTURE"))
        translate()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "APPROVED_FIXTURE" }
        assertTrue(ApprovedCorrectionRepository(activity).getAll().isEmpty())
        view(R.id.btnApproveQuickTeacher).performClick()
        waitFor { text(R.id.btnApproveQuickTeacher) == activity.getString(R.string.correction_saved) }
        assertFalse(view(R.id.btnApproveQuickTeacher).isEnabled)
        view(R.id.btnApproveQuickTeacher).performClick()
        val freshRepository = ApprovedCorrectionRepository(activity)
        assertEquals(1, freshRepository.getAll().size)
        val exported = JSONObject(freshRepository.exportTrainingJsonl().trim())
        assertEquals("user-approved", exported.getString("review_status"))
        assertEquals("STUDENT_FIXTURE", exported.getString("student_translation"))
        assertEquals("APPROVED_FIXTURE", exported.getJSONArray("messages").getJSONObject(2).getString("content"))
        val freshService = TranslationService(activity)
        val next = ChatMessage("next", "Tester", "", "  SOURCE  FIXTURE  ")
        assertEquals("APPROVED_FIXTURE", runBlocking { freshService.translateMessage(next) })
        assertTrue(next.usedApprovedCorrection)
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = false
        translate()
        waitFor { text(R.id.tvQuickResult) == "APPROVED_FIXTURE" }
        assertEquals(activity.getString(R.string.saved_translation_title), text(R.id.tvQuickTranslationLabel))
        assertEquals(1, requests.size)
    }

    @Test fun forgettingACorrectionRemovesItFromReuseAndTrainingExport() {
        enqueue(review("match", "APPROVED_FIXTURE"))
        translate()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "APPROVED_FIXTURE" }
        view(R.id.btnApproveQuickTeacher).performClick()
        waitFor { view(R.id.btnForgetQuickCorrection).visibility == View.VISIBLE }
        view(R.id.btnForgetQuickCorrection).performClick()
        waitFor { view(R.id.btnApproveQuickTeacher).isEnabled }
        assertEquals("", ApprovedCorrectionRepository(activity).exportTrainingJsonl())
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = false
        translate()
        waitFor { text(R.id.tvQuickResult) == "STUDENT_FIXTURE" }
        assertEquals(activity.getString(R.string.local_translation_title), text(R.id.tvQuickTranslationLabel))
    }

    @Test fun aNewApprovalReplacesTheOldMeaningWithoutContradictoryTrainingRows() {
        val repo = ApprovedCorrectionRepository(activity)
        repo.save("source fixture", "OLD_STUDENT", "OLD_CORRECTION", "")
        repo.save(" SOURCE  FIXTURE ", "NEW_STUDENT", "NEW_CORRECTION", "")
        assertEquals(1, repo.getAll().size)
        assertEquals("NEW_CORRECTION", repo.find("source fixture")!!.correctedTranslation)
        assertFalse(repo.remove("source fixture", "OLD_CORRECTION"))
        assertEquals(1, repo.exportTrainingJsonl().lineSequence().filter { it.isNotBlank() }.count())
        val row = JSONObject(repo.exportTrainingJsonl().trim())
        assertEquals("NEW_CORRECTION", row.getJSONArray("messages").getJSONObject(2).getString("content"))
    }

    @Test fun savedKeysStillRequireEnablingReviewAndSavingSettingsChecksTheExistingAnswer() {
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = false
        translate()
        waitFor { view(R.id.quickTeacherCard).visibility == View.VISIBLE }
        assertEquals(activity.getString(R.string.quick_teacher_off), text(R.id.tvQuickTeacherStatus))
        assertTrue(requests.isEmpty())
        view(R.id.btnQuickTeacherSettings).performClick()
        assertEquals(View.VISIBLE, view(R.id.viewModelTab).visibility)
        assertEquals(View.VISIBLE, view(R.id.cloudSettings).visibility)
        activity.findViewById<EditText>(R.id.etGeminiKey).setText("")
        view(R.id.btnSaveTeacherSettings).performClick()
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = true
        assertEquals(activity.getString(R.string.quick_teacher_missing_key), text(R.id.tvQuickTeacherStatus))
        assertTrue(requests.isEmpty())
        enqueue(review("match", "TEACHER_FIXTURE"))
        activity.findViewById<EditText>(R.id.etGeminiKey).setText("REPLACEMENT_KEY_FIXTURE")
        view(R.id.btnSaveTeacherSettings).performClick()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "TEACHER_FIXTURE" }
        assertEquals(1, requests.size)
        assertEquals("STUDENT_FIXTURE", text(R.id.tvQuickResult))
    }

    @Test fun quotaErrorsRemainVisibleAndRetryCanRecoverWithoutRetranslating() {
        enqueue(code = 429)
        translate()
        waitFor { text(R.id.tvQuickTeacherStatus) == activity.getString(R.string.quick_teacher_unavailable) }
        assertTrue(text(R.id.tvQuickTeacherExplanation).contains("429"))
        assertTrue(text(R.id.tvQuickTeacherExplanation).contains("quota"))
        assertEquals("STUDENT_FIXTURE", text(R.id.tvQuickResult))
        assertEquals(View.GONE, view(R.id.btnCopyQuickTeacher).visibility)
        assertEquals(View.VISIBLE, view(R.id.btnRetryQuickTeacher).visibility)
        assertEquals(View.GONE, view(R.id.btnApproveQuickTeacher).visibility)
        enqueue(review("match", "RECOVERED_FIXTURE"))
        view(R.id.btnRetryQuickTeacher).performClick()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "RECOVERED_FIXTURE" }
        assertEquals(2, requests.size)
        assertEquals("STUDENT_FIXTURE", text(R.id.tvQuickResult))
    }

    @Test fun invalidGeminiReviewShowsFailureHelpInsteadOfApprovingTheStudent() {
        enqueue("{}")
        translate()
        waitFor { view(R.id.btnRetryQuickTeacher).visibility == View.VISIBLE }
        assertEquals(listOf("generativelanguage.googleapis.com"), requests.map { it.url.host })
        assertEquals(activity.getString(R.string.quick_teacher_unavailable), text(R.id.tvQuickTeacherStatus))
    }

    @Test fun aLateReviewCannotReappearAfterClearingOrOverwriteTheNextTranslation() {
        val old = enqueue(review("match", "STALE_TEACHER_FIXTURE"), blocked = true)
        translate()
        waitFor { old.started.count == 0L }
        view(R.id.btnClearPasteText).performClick()
        assertEquals(View.GONE, view(R.id.quickResultCard).visibility)
        assertEquals(View.GONE, view(R.id.quickTeacherCard).visibility)
        assertEquals("", text(R.id.tvQuickTeacherTranslation))
        enqueue(review("match", "NEW_TEACHER_FIXTURE"))
        translate("second source fixture")
        waitFor { text(R.id.tvQuickTeacherTranslation) == "NEW_TEACHER_FIXTURE" }
        old.release.countDown()
        waitFor { old.finished.count == 0L }
        assertEquals("NEW_TEACHER_FIXTURE", text(R.id.tvQuickTeacherTranslation))
        assertEquals("SECOND_STUDENT_FIXTURE", text(R.id.tvQuickResult))
    }

    @Test fun disablingCloudReviewDuringARequestPreventsLateResultsAndFallbackRequests() {
        val old = enqueue(code = 503, blocked = true)
        translate()
        waitFor { old.started.count == 0L }
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = false
        assertEquals(activity.getString(R.string.quick_teacher_off), text(R.id.tvQuickTeacherStatus))
        old.release.countDown()
        waitFor { old.finished.count == 0L }
        assertEquals(activity.getString(R.string.quick_teacher_off), text(R.id.tvQuickTeacherStatus))
        assertEquals(View.GONE, view(R.id.btnCopyQuickTeacher).visibility)
        assertEquals(1, requests.size)
    }

    @Test fun tuluUsesTheTeacherDirectlyAndReusesItsApprovedMeaningOffline() {
        view(R.id.btnLanguageTulu).performClick()
        enqueue(review("match", "TULU_CORRECTION_FIXTURE"))
        translate()
        waitFor { text(R.id.tvQuickTeacherTranslation) == "TULU_CORRECTION_FIXTURE" }
        assertEquals(View.GONE, view(R.id.quickResultCard).visibility)
        assertEquals(activity.getString(R.string.tulu_teacher_result), text(R.id.tvQuickTeacherStatus))
        val prompt = JSONObject(requests.single().body).getJSONArray("contents").getJSONObject(0)
            .getJSONArray("parts").getJSONObject(0).getString("text")
        val input = JSONObject(prompt.substringAfter("Input JSON:").trim())
        assertEquals("tcy-Latn", input.getString("sourceLanguage"))
        assertEquals("", input.getString("studentEnglish"))
        assertTrue(prompt.contains("Tulu written in Latin letters"))
        view(R.id.btnApproveQuickTeacher).performClick()
        waitFor { text(R.id.btnApproveQuickTeacher) == activity.getString(R.string.correction_saved) }
        val repo = ApprovedCorrectionRepository(activity)
        assertNull(repo.find("source fixture", SourceLanguage.KANGLISH))
        assertEquals("TULU_CORRECTION_FIXTURE", repo.find("source fixture", SourceLanguage.TULU)!!.correctedTranslation)
        val exported = JSONObject(repo.exportTrainingJsonl(SourceLanguage.TULU).trim())
        assertEquals("tcy-Latn", exported.getString("source_language"))
        assertEquals("", exported.getString("student_translation"))
        assertTrue(exported.getJSONArray("messages").getJSONObject(0).getString("content").contains("Tulu"))
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = false
        translate()
        waitFor { text(R.id.tvQuickResult) == "TULU_CORRECTION_FIXTURE" }
        assertEquals(activity.getString(R.string.saved_translation_title), text(R.id.tvQuickTranslationLabel))
        view(R.id.btnLanguageKannada).performClick()
        assertEquals(View.GONE, view(R.id.quickResultCard).visibility)
        translate()
        waitFor { text(R.id.tvQuickResult) == "STUDENT_FIXTURE" }
        assertEquals(1, requests.size)
    }

    @Test fun tuluWithoutCloudNeverFallsBackToTheKannadaGlossaryOrModel() {
        activity.findViewById<SwitchMaterial>(R.id.switchTeacherEnabled).isChecked = false
        view(R.id.btnLanguageTulu).performClick()
        translate()
        waitFor { text(R.id.tvQuickTeacherStatus) == activity.getString(R.string.quick_teacher_off) }
        assertEquals(View.GONE, view(R.id.quickResultCard).visibility)
        assertEquals(View.GONE, view(R.id.btnApproveQuickTeacher).visibility)
        assertTrue(requests.isEmpty())
        val result = runCatching { runBlocking {
            TranslationService(activity).translateMessage(ChatMessage("tulu", "Tester", "", "source fixture", language = SourceLanguage.TULU))
        } }
        assertTrue(result.exceptionOrNull() is IllegalArgumentException)
    }

    @Test fun switchingLanguageDiscardsAnInFlightTuluResponse() {
        view(R.id.btnLanguageTulu).performClick()
        val pending = enqueue(review("match", "STALE_TULU_FIXTURE"), blocked = true)
        translate()
        waitFor { pending.started.count == 0L }
        view(R.id.btnLanguageKannada).performClick()
        pending.release.countDown()
        waitFor { pending.finished.count == 0L }
        assertEquals(View.GONE, view(R.id.quickTeacherCard).visibility)
        assertEquals("", text(R.id.tvQuickTeacherTranslation))
        assertEquals(activity.getString(R.string.kanglish_heading), text(R.id.tvQuickHeading))
        assertTrue(ApprovedCorrectionRepository(activity).getAll().isEmpty())
    }

    @Test fun legacyKannadaCorrectionsAndSameSpellingTuluCorrectionsStaySeparate() {
        val repo = ApprovedCorrectionRepository(activity)
        repo.save("same source fixture", "STUDENT", "KANNADA_CORRECTION_FIXTURE", "")
        val file = File(activity.filesDir, "approved_teacher_corrections.json")
        val legacy = JSONArray(file.readText())
        legacy.getJSONObject(0).remove("source_language")
        file.writeText(legacy.toString())
        assertEquals("KANNADA_CORRECTION_FIXTURE", ApprovedCorrectionRepository(activity).find("same source fixture")!!.correctedTranslation)
        repo.save("same source fixture", "", "TULU_CORRECTION_FIXTURE", "", SourceLanguage.TULU)
        assertEquals(2, repo.getAll().size)
        assertEquals("KANNADA_CORRECTION_FIXTURE", repo.find("same source fixture", SourceLanguage.KANGLISH)!!.correctedTranslation)
        assertEquals("TULU_CORRECTION_FIXTURE", repo.find("same source fixture", SourceLanguage.TULU)!!.correctedTranslation)
        assertEquals(1, repo.exportTrainingJsonl(SourceLanguage.TULU).lineSequence().filter { it.isNotBlank() }.count())
        assertTrue(repo.remove("same source fixture", "TULU_CORRECTION_FIXTURE", SourceLanguage.TULU))
        assertEquals(1, repo.getAll().size)
        assertNotNull(repo.find("same source fixture", SourceLanguage.KANGLISH))
    }

    private fun view(id: Int): View = activity.findViewById(id)
    private fun text(id: Int) = activity.findViewById<TextView>(id).text.toString()

    private fun translate(source: String = "source fixture") {
        activity.findViewById<EditText>(R.id.etPasteInput).setText(source)
        view(R.id.btnParsePaste).performClick()
    }

    private fun enqueue(review: String = "", code: Int = 200, blocked: Boolean = false): Reply {
        val reply = Reply(review, code, CountDownLatch(if (blocked) 1 else 0))
        allReplies.add(reply)
        replies.add(reply)
        return reply
    }

    private fun review(verdict: String, translation: String, explanation: String = "") = JSONObject()
        .put("verdict", verdict).put("teacherTranslation", translation).put("explanation", explanation).toString()

    private fun envelope(url: URL, review: String): String =
        JSONObject().put("candidates", JSONArray().put(JSONObject().put("content",
            JSONObject().put("parts", JSONArray().put(JSONObject().put("text", review)))))).toString()

    private fun waitFor(condition: () -> Boolean) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        do {
            shadowOf(Looper.getMainLooper()).idle()
            if (condition()) return
            Thread.sleep(10)
        } while (System.nanoTime() < deadline)
        fail("Timed out waiting for the translation/review UI")
    }
}
