package org.kanglish.app.data

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

data class DictionaryEntry(val original: String, val english: String, val language: SourceLanguage)

/** Explicitly imported translation pairs, never unlabeled chat or guessed labels. */
object PersonalDictionary {
    private val whitespace = Regex("\\s+")
    private val words = Regex("[\\p{L}\\p{M}\\p{N}]+")
    fun key(text: String) = text.trim().lowercase(Locale.ROOT).replace(whitespace, " ")

    fun relevant(text: String, language: SourceLanguage, entries: List<ApprovedCorrection>, limit: Int = 8): List<ApprovedCorrection> {
        val tokens = words.findAll(key(text)).map { it.value }.toSet()
        val normalized = " ${words.findAll(key(text)).joinToString(" ") { it.value }} "
        return entries.asSequence().filter { language == SourceLanguage.MIXED || it.language == language || it.language == SourceLanguage.MIXED }
            .map { entry ->
                val sourceTokens = words.findAll(key(entry.originalText)).map { it.value }.toList()
                val exact = normalized.contains(" ${sourceTokens.joinToString(" ")} ")
                val overlap = sourceTokens.count { it in tokens }
                entry to (if (exact) 1000 + sourceTokens.size else overlap)
            }.filter { it.second > 0 }.sortedByDescending { it.second }.take(limit).map { it.first }.toList()
    }

    fun parse(text: String, defaultLanguage: SourceLanguage): List<DictionaryEntry> {
        require(text.length <= 2_000_000) { "Choose a dataset under 2 MB." }
        val clean = text.trim().removePrefix("\uFEFF")
        val rows = when {
            clean.startsWith("[") -> JSONArray(clean).let { a -> (0 until a.length()).map { a.getJSONObject(it) } }
            clean.startsWith("{") -> clean.lineSequence().filter { it.isNotBlank() }.map { JSONObject(it) }.toList()
            else -> {
                val csv = csvRows(clean)
                require(csv.size >= 2) { "Use CSV with original,english headers, or JSON / JSONL translation pairs." }
                val headers = csv.first().map { it.trim().lowercase(Locale.ROOT) }
                csv.drop(1).filter { row -> row.any { it.isNotBlank() } }.map { row ->
                    require(row.size == headers.size) { "A CSV row has the wrong number of columns." }
                    JSONObject().apply { headers.forEachIndexed { i, header -> put(header, row[i]) } }
                }
            }
        }
        require(rows.isNotEmpty() && rows.size <= 5000) { "Import between 1 and 5,000 translation pairs at a time." }
        val entries = rows.mapIndexed { index, row ->
            fun field(vararg names: String): String = names.firstNotNullOfOrNull { name -> (row.opt(name) as? String)?.takeIf { it.isNotBlank() } }.orEmpty()
            val messages = row.optJSONArray("messages")
            fun message(role: String): String = messages?.let { a -> (0 until a.length()).map { a.getJSONObject(it) }
                .firstOrNull { it.optString("role") == role }?.optString("content") }.orEmpty()
            val original = field("original", "original_text", "kanglish", "input").ifBlank { message("user") }.trim()
            val english = field("english", "corrected_translation", "output", "answer").ifBlank { message("assistant") }.trim()
            require(original.isNotBlank() && english.isNotBlank() && original.length <= 4000 && english.length <= 4000) {
                "Row ${index + 1} needs original text and an English meaning, each under 4,000 characters."
            }
            val id = field("source_language", "language")
            DictionaryEntry(original, english, if (id.isBlank()) defaultLanguage else SourceLanguage.fromId(id))
        }
        val grouped = entries.groupBy { it.language.id to key(it.original) }
        require(grouped.values.none { group -> group.map { it.english }.distinct().size > 1 }) { "The dataset contains conflicting meanings for the same phrase. Resolve them before importing." }
        return grouped.values.map { it.first() }
    }

    private fun csvRows(text: String): List<List<String>> {
        val rows = mutableListOf<List<String>>()
        var row = mutableListOf<String>()
        val cell = StringBuilder()
        var quoted = false
        var i = 0
        while (i < text.length) {
            val c = text[i]
            when {
                c == '"' -> if (quoted && text.getOrNull(i + 1) == '"') { cell.append('"'); i++ } else quoted = !quoted
                c == ',' && !quoted -> { row += cell.toString(); cell.clear() }
                (c == '\n' || c == '\r') && !quoted -> {
                    row += cell.toString(); cell.clear(); rows += row; row = mutableListOf()
                    if (c == '\r' && text.getOrNull(i + 1) == '\n') i++
                }
                else -> cell.append(c)
            }
            i++
        }
        require(!quoted) { "The CSV has an unclosed quoted field." }
        if (cell.isNotEmpty() || row.isNotEmpty()) { row += cell.toString(); rows += row }
        return rows
    }
}
