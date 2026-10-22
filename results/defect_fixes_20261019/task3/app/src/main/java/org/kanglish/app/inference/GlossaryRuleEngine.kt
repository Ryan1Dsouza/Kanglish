package org.kanglish.app.inference

import org.kanglish.app.data.GlossaryManager
import java.util.Locale

class GlossaryRuleEngine(private val entries: () -> List<Pair<String, String>>) {
    constructor(glossaryManager: GlossaryManager) : this({ glossaryManager.getEntries() })

    fun exactTranslation(text: String): String? {
        val normalized = text.trim().replace(Regex("\\s+"), " ")
        return entries().firstOrNull { (source, _) ->
            source.trim().replace(Regex("\\s+"), " ").equals(normalized, ignoreCase = true)
        }?.second
    }

    fun translate(kanglishText: String): String {
        val trimmed = kanglishText.trim()
        if (trimmed.isEmpty()) return ""

        // 0. Detach emojis and collapse elongated letters (e.g., "muchoooo🔥" -> "mucho 🔥")
        val detachedEmojis = trimmed.replace(Regex("([\\uD800-\\uDBFF][\\uDC00-\\uDFFF]|[\\u2600-\\u27BF])"), " $1 ")
            .replace(Regex("\\s+"), " ")
        val lower = detachedEmojis.lowercase(Locale.ROOT)
        val normalizedLower = lower.replace(Regex("([a-z])\\1+"), "$1")

        // 1. Direct exact or multi-word phrase matching from reviewed glossary
        for ((k, e) in entries()) {
            val kLower = k.lowercase(Locale.ROOT)
            val normK = kLower.replace(Regex("([a-z])\\1+"), "$1")
            if (lower == kLower || normalizedLower == normK) {
                // If there are emojis in the input, append them to the translated phrase
                val emojis = extractEmojis(trimmed)
                return if (emojis.isNotEmpty()) "$e $emojis" else e
            }
        }

        // 2. Token-by-token and multi-word token replacement preserving English phrases & punctuation
        var working = detachedEmojis

        // Replace multi-word entries first (already sorted by length descending)
        for ((k, e) in entries()) {
            if (k.contains(" ")) {
                val regex = "(?i)\\b${Regex.escape(k)}\\b".toRegex()
                working = working.replace(regex, e)
            }
        }

        // Apply grammatical and morphological rule transformations
        val tokens = working.split(Regex("(?<=\\s)|(?=\\s)|(?<=[.,!?])|(?=[.,!?])"))
        val result = StringBuilder()

        for (token in tokens) {
            val tokenClean = token.trim()
            if (tokenClean.isEmpty() || tokenClean.matches(Regex("[.,!?]+"))) {
                result.append(token)
                continue
            }

            var replacement: String? = null
            for ((k, e) in entries()) {
                if (!k.contains(" ") && tokenClean.equals(k, ignoreCase = true)) {
                    // Extract primary meaning if contains slash (e.g. "bro/dude" -> "bro")
                    replacement = e.split("/")[0].split("(")[0].trim()
                    break
                }
            }

            if (replacement != null) {
                // Preserve capitalization if first letter was capitalized
                if (tokenClean[0].isUpperCase()) {
                    replacement = replacement.replaceFirstChar { it.uppercase() }
                }
                result.append(replacement)
            } else {
                // Retain original word (English words, names, unlisted vocabulary)
                result.append(tokenClean)
            }
            if (token.endsWith(" ")) {
                result.append(" ")
            }
        }

        var translated = result.toString().trim()

        // Clean up common translation artifacts
        translated = translated.replace(Regex("\\s+"), " ")
        translated = translated.replace(" ,", ",").replace(" .", ".").replace(" ?", "?")
        val finalResult = translated.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }

        if (finalResult.equals(trimmed, ignoreCase = true)) {
            return "$finalResult [Glossary: No match. Load AI model in Model tab]"
        }
        return finalResult
    }

    private fun extractEmojis(text: String): String {
        val emojiRegex = "([\\uD800-\\uDBFF][\\uDC00-\\uDFFF]|[\\u2600-\\u27BF])".toRegex()
        return emojiRegex.findAll(text).map { it.value }.joinToString(" ")
    }
}
