package org.kanglish.app.data

import android.content.Context
import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileNotFoundException
import java.io.IOException
import java.util.Locale

data class ApprovedCorrection(
    val originalText: String,
    val generatedTranslation: String,
    val correctedTranslation: String,
    val teacherExplanation: String,
    val approvedAt: Long,
    val language: SourceLanguage = SourceLanguage.KANGLISH,
    val source: String = "app_teacher_approval"
)

/** Only explicit user approvals enter this store. Reads are shared across app entry points. */
class ApprovedCorrectionRepository(context: Context) {
    private val file = AtomicFile(File(context.applicationContext.filesDir, "approved_teacher_corrections.json"))

    companion object {
        private val lock = Any()
        private fun key(text: String) = text.trim().replace(Regex("\\s+"), " ").lowercase(Locale.ROOT)
    }

    fun getAll(): List<ApprovedCorrection> = synchronized(lock) { readAll() }

    /** Import is all-or-nothing; existing personal meanings win on conflicts. */
    fun importEntries(entries: List<DictionaryEntry>): Int = synchronized(lock) {
        val current = readAll()
        val keys = current.map { it.language.id to key(it.originalText) }.toMutableSet()
        val additions = entries.filter { keys.add(it.language.id to key(it.original)) }.map {
            require(it.original.isNotBlank() && it.english.isNotBlank() && it.original.length <= 4000 && it.english.length <= 4000)
            ApprovedCorrection(it.original.trim(), "", it.english.trim(), "Imported personal dataset", System.currentTimeMillis(), it.language, "user_dataset")
        }
        if (additions.isNotEmpty()) writeAll(additions + current)
        additions.size
    }

    fun find(originalText: String, language: SourceLanguage = SourceLanguage.KANGLISH): ApprovedCorrection? = synchronized(lock) {
        val matches = readAll().filter { key(it.originalText) == key(originalText) }
        matches.firstOrNull { it.language == language } ?: if (language == SourceLanguage.MIXED &&
            matches.map { it.correctedTranslation }.distinct().size == 1) matches.firstOrNull() else null
    }

    fun save(
        originalText: String,
        generatedTranslation: String,
        correctedTranslation: String,
        teacherExplanation: String,
        language: SourceLanguage = SourceLanguage.KANGLISH,
        source: String = "app_teacher_approval"
    ): ApprovedCorrection = synchronized(lock) {
        require(originalText.isNotBlank() && correctedTranslation.isNotBlank()) { "A message and a correction are required." }
        require(source in setOf("app_teacher_approval", "user_dictionary", "user_dataset"))
        require(originalText.length <= 4000 && correctedTranslation.length <= 4000) { "Use entries under 4,000 characters." }
        require(source != "app_teacher_approval" || language != SourceLanguage.KANGLISH || generatedTranslation.isNotBlank()) { "Translate the message before approving a correction." }
        val current = readAll()
        val existing = current.firstOrNull { it.language == language && key(it.originalText) == key(originalText) }
        if (existing?.correctedTranslation == correctedTranslation.trim()) return@synchronized existing
        val correction = ApprovedCorrection(originalText.trim(), generatedTranslation.trim(), correctedTranslation.trim(),
            teacherExplanation.trim(), System.currentTimeMillis(), language, source)
        writeAll(listOf(correction) + current.filterNot { it.language == language && key(it.originalText) == key(originalText) })
        correction
    }

    /** The expected meaning prevents an older screen from deleting a newer approval. */
    fun remove(originalText: String, expectedMeaning: String, language: SourceLanguage = SourceLanguage.KANGLISH): Boolean = synchronized(lock) {
        val current = readAll()
        val remaining = current.filterNot { it.language == language && key(it.originalText) == key(originalText) && it.correctedTranslation == expectedMeaning }
        if (remaining.size == current.size) return@synchronized false
        writeAll(remaining)
        true
    }

    fun exportTrainingJsonl(language: SourceLanguage? = null): String = synchronized(lock) {
        val records = readAll().filter { language == null || it.language == language }
        records.joinToString(separator = "\n", postfix = if (records.isEmpty()) "" else "\n") { record ->
            JSONObject().apply {
                put("schema_version", 1)
                put("source_language", record.language.id)
                put("source", record.source)
                put("review_status", "user-approved")
                put("approved_at_ms", record.approvedAt)
                put("original_text", record.originalText)
                put("student_translation", record.generatedTranslation)
                put("teacher_explanation", record.teacherExplanation)
                put("messages", JSONArray().apply {
                    put(JSONObject().put("role", "system").put("content", record.language.trainingInstruction))
                    put(JSONObject().put("role", "user").put("content", record.originalText.replace("<|", "< |")))
                    put(JSONObject().put("role", "assistant").put("content", record.correctedTranslation.replace("<|", "< |")))
                })
            }.toString()
        }
    }

    private fun readAll(): List<ApprovedCorrection> {
        val text = try {
            file.openRead().bufferedReader(Charsets.UTF_8).use { it.readText() }
        } catch (e: FileNotFoundException) {
            if (file.baseFile.exists()) throw IOException("Could not read saved corrections.", e)
            return emptyList()
        }
        return try {
            val array = JSONArray(text)
            (0 until array.length()).map { index ->
                val row = array.getJSONObject(index)
                require(row.opt("user_approved") == true)
                val original = row.getString("original_text")
                val student = row.getString("student_translation")
                val correction = row.getString("corrected_translation")
                val language = SourceLanguage.fromId(row.optString("source_language", SourceLanguage.KANGLISH.id))
                val source = row.optString("source", "app_teacher_approval")
                require(original.isNotBlank() && correction.isNotBlank() &&
                    (source != "app_teacher_approval" || language != SourceLanguage.KANGLISH || student.isNotBlank()))
                ApprovedCorrection(original, student, correction, row.getString("teacher_explanation"), row.getLong("approved_at_ms"), language, source)
            }
        } catch (e: Exception) {
            throw IOException("Could not read saved corrections. The existing file has been kept.", e)
        }
    }

    private fun writeAll(records: List<ApprovedCorrection>) {
        val array = JSONArray()
        records.forEach { record ->
            array.put(JSONObject().apply {
                put("user_approved", true)
                put("source", record.source)
                put("source_language", record.language.id)
                put("original_text", record.originalText)
                put("student_translation", record.generatedTranslation)
                put("corrected_translation", record.correctedTranslation)
                put("teacher_explanation", record.teacherExplanation)
                put("approved_at_ms", record.approvedAt)
            })
        }
        val output = file.startWrite()
        try {
            output.write(array.toString(2).toByteArray(Charsets.UTF_8))
            file.finishWrite(output)
        } catch (e: Exception) {
            file.failWrite(output)
            throw IOException("Could not save the correction. Try again.", e)
        }
    }
}
