package org.kanglish.app

import android.view.ContextThemeWrapper
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.data.MessageStatus
import org.kanglish.app.inference.TeacherResponseParser
import org.kanglish.app.ui.MessageAdapter
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class TeacherResponseTest {
    private val match = """{"verdict":"match","teacherTranslation":"OUTPUT_FIXTURE","explanation":""}"""

    @Test fun emptyOrOldResponsesCannotApproveTheStudent() {
        for (raw in listOf("{}", "null", "[]", "", """{"isMatch":true}""")) {
            assertNull(raw, TeacherResponseParser.parse(raw))
        }
    }

    @Test fun agreementRequiresAnExplicitVerdictAndTranslation() {
        val result = TeacherResponseParser.parse(match)!!
        assertTrue(result.success)
        assertTrue(result.isMatch)
        assertFalse(result.isUncertain)
        assertEquals("OUTPUT_FIXTURE", result.teacherTranslation)
    }

    @Test fun wrongTypesUnknownVerdictsAndBlankTranslationsAreRejected() {
        for (raw in listOf(
            match.replace("\"match\"", "true"),
            match.replace("\"match\"", "\"probably\""),
            match.replace("\"OUTPUT_FIXTURE\"", "null"),
            match.replace("\"OUTPUT_FIXTURE\"", "42"),
            match.replace("\"OUTPUT_FIXTURE\"", "\"  \""),
            match.replace("\"explanation\":\"\"", "\"explanation\":false")
        )) assertNull(raw, TeacherResponseParser.parse(raw))
    }

    @Test fun mismatchRequiresBothACorrectionAndAReason() {
        val invalid = match.replace("\"match\"", "\"mismatch\"")
        assertNull(TeacherResponseParser.parse(invalid))
        val valid = invalid.replace("\"explanation\":\"\"", "\"explanation\":\"REASON_FIXTURE\"")
        val result = TeacherResponseParser.parse(valid)!!
        assertFalse(result.isMatch)
        assertFalse(result.isUncertain)
        assertEquals("OUTPUT_FIXTURE", result.teacherTranslation)
    }

    @Test fun uncertaintyIsExplicitAndNeverContainsALearnedAnswer() {
        val raw = """{"verdict":"uncertain","teacherTranslation":"","explanation":"CONTEXT_REQUIRED_FIXTURE"}"""
        val result = TeacherResponseParser.parse(raw)!!
        assertTrue(result.success)
        assertTrue(result.isUncertain)
        assertFalse(result.isMatch)
        assertEquals("", result.teacherTranslation)
        assertNull(TeacherResponseParser.parse(raw.replace("\"teacherTranslation\":\"\"", "\"teacherTranslation\":\"GUESS\"")))
        assertNull(TeacherResponseParser.parse(raw.replace("CONTEXT_REQUIRED_FIXTURE", "")))
    }

    @Test fun wholeCodeFenceIsAllowedButExtraResponseTextIsRejected() {
        assertNotNull(TeacherResponseParser.parse("```json\n$match\n```"))
        assertNull(TeacherResponseParser.parse("Here is my answer: $match"))
        assertNull(TeacherResponseParser.parse("$match {}"))
        assertNull(TeacherResponseParser.parse("$match trailing commentary"))
    }

    @Test fun uncertainReviewHidesSaveMeaningAndShowsItsReason() {
        val context = ContextThemeWrapper(RuntimeEnvironment.getApplication(), R.style.Theme_Kanglish)
        val adapter = MessageAdapter({ _, _ -> }, { _, _ -> })
        adapter.submitList(listOf(ChatMessage(
            id = "fixture", sender = "Fixture", timestamp = "", originalText = "SOURCE_FIXTURE",
            translatedText = "OUTPUT_FIXTURE", status = MessageStatus.TRANSLATED,
            isTeacherChecked = true, isTeacherMatch = false, isTeacherUncertain = true,
            teacherExplanation = "CONTEXT_REQUIRED_FIXTURE"
        )))
        val holder = adapter.onCreateViewHolder(FrameLayout(context), 0)
        adapter.onBindViewHolder(holder, 0)
        assertEquals(View.GONE, holder.itemView.findViewById<View>(R.id.btnTeachModel).visibility)
        assertEquals("UNCERTAIN", holder.itemView.findViewById<TextView>(R.id.tvTeacherBadge).text.toString())
        assertEquals("CONTEXT_REQUIRED_FIXTURE", holder.itemView.findViewById<TextView>(R.id.tvTeacherText).text.toString())
    }
}
