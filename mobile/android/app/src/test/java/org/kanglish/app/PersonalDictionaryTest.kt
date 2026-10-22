package org.kanglish.app

import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.data.*
import org.kanglish.app.inference.TeacherService
import org.kanglish.app.inference.TranslationService
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.json.JSONObject

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class PersonalDictionaryTest {
    private val app get() = RuntimeEnvironment.getApplication()

    @Test fun manualMeaningsWorkOfflineWithoutAPreviousModelAnswerAndExportTheirProvenance() {
        val repo = ApprovedCorrectionRepository(app)
        repo.save("SOURCE_FIXTURE", "", "MEANING_FIXTURE", "", SourceLanguage.TULU, "user_dictionary")
        val service = TranslationService(app)
        assertEquals("MEANING_FIXTURE", runBlocking { service.translateMessage(ChatMessage("1", "", "", " source_fixture ", language = SourceLanguage.MIXED)) })
        val exported = JSONObject(repo.exportTrainingJsonl().trim())
        assertEquals("user_dictionary", exported.getString("source"))
        assertEquals("tcy-Latn", exported.getString("source_language"))
        assertEquals("MEANING_FIXTURE", PersonalDictionary.parse(repo.exportTrainingJsonl(), SourceLanguage.KANGLISH).single().english)
    }

    @Test fun mixedModeDoesNotChooseBetweenConflictingLanguageMeanings() {
        val repo = ApprovedCorrectionRepository(app)
        repo.save("source", "", "FIRST", "", SourceLanguage.TULU, "user_dictionary")
        repo.save("source", "", "SECOND", "", SourceLanguage.KANGLISH, "user_dictionary")
        assertNull(repo.find("source", SourceLanguage.MIXED))
        assertEquals("FIRST", repo.find("source", SourceLanguage.TULU)!!.correctedTranslation)
    }

    @Test fun csvSupportsQuotedCommasNewlinesAndExistingMeaningsSurviveImport() {
        val text = "original,english,source_language\r\n\"source, one\",\"meaning\nline two\",tcy-Latn\r\nsource2,meaning2,mixed"
        val rows = PersonalDictionary.parse(text, SourceLanguage.KANGLISH)
        assertEquals("meaning\nline two", rows.first().english)
        val repo = ApprovedCorrectionRepository(app)
        repo.save("source2", "", "KEEP", "", SourceLanguage.MIXED, "user_dictionary")
        assertEquals(1, repo.importEntries(rows))
        assertEquals(0, repo.importEntries(rows))
        assertEquals("KEEP", repo.find("source2", SourceLanguage.MIXED)!!.correctedTranslation)
    }

    @Test fun badOrConflictingDatasetsAreRejectedBeforeSaving() {
        listOf("original,english\na,", "original,english\na,ONE\na,TWO", "[{\"original\":\"a\",\"english\":4}]").forEach {
            try { PersonalDictionary.parse(it, SourceLanguage.TULU); fail("Accepted invalid input") } catch (_: IllegalArgumentException) { }
        }
        assertTrue(ApprovedCorrectionRepository(app).getAll().isEmpty())
    }

    @Test fun teacherReceivesRelevantLanguageScopedKnowledgeAsDataAndUpdatesAfterEdits() {
        val repo = ApprovedCorrectionRepository(app)
        repo.save("source", "", "MY_MEANING", "", SourceLanguage.TULU, "user_dictionary")
        repo.save("unrelated", "", "UNRELATED", "", SourceLanguage.TULU, "user_dictionary")
        val teacher = TeacherService(app)
        fun references() = JSONObject(teacher.reviewPrompt("source please", "", SourceLanguage.TULU).substringAfter("Input JSON:").trim())
            .getJSONArray("referenceTranslations").toString()
        assertTrue(references().contains("MY_MEANING"))
        assertFalse(references().contains("UNRELATED"))
        repo.save("source", "", "EDITED", "", SourceLanguage.TULU, "user_dictionary")
        assertTrue(references().contains("EDITED"))
        repo.remove("source", "EDITED", SourceLanguage.TULU)
        assertFalse(references().contains("EDITED"))
    }

    @Test fun directAudioTranslationRespectsCloudSwitchEvenWithSavedKey() {
        var calls = 0
        val teacher = TeacherService(app) { calls++; error("Unexpected network request") }
        teacher.geminiKey = "FIXTURE_KEY"
        teacher.isTeacherEnabled = false
        assertNull(runBlocking { teacher.translateDirect("source") })
        assertEquals(0, calls)
    }
}
