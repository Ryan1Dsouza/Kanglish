package org.kanglish.app.inference

import org.json.JSONObject
import org.json.JSONTokener

/** A successful HTTP request is not necessarily a usable review. */
internal object TeacherResponseParser {
    fun parse(raw: String): TeacherResult? {
        if (raw.length > 32_768) return null
        var clean = raw.trim()
        val fence = Regex("^```(?:json)?\\s*([\\s\\S]*?)\\s*```$", RegexOption.IGNORE_CASE)
        fence.matchEntire(clean)?.let { clean = it.groupValues[1].trim() }
        return try {
            val tokenizer = JSONTokener(clean)
            val json = tokenizer.nextValue() as? JSONObject ?: return null
            if (tokenizer.nextClean() != '\u0000') return null
            val verdict = json.opt("verdict") as? String ?: return null
            val translation = (json.opt("teacherTranslation") as? String)?.trim() ?: return null
            val explanation = (json.opt("explanation") as? String)?.trim() ?: return null
            if (verdict !in setOf("match", "mismatch", "uncertain")) return null
            val uncertain = verdict == "uncertain"
            if (uncertain && (translation.isNotEmpty() || explanation.isEmpty())) return null
            if (!uncertain && translation.isEmpty()) return null
            if (verdict == "mismatch" && explanation.isEmpty()) return null
            TeacherResult(
                success = true,
                isMatch = verdict == "match",
                teacherTranslation = translation,
                explanation = explanation,
                isUncertain = uncertain
            )
        } catch (_: Exception) {
            null
        }
    }
}
