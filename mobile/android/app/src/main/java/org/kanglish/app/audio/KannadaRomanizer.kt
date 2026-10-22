package org.kanglish.app.audio

import java.text.Normalizer

/** Deterministic phonetic Kannada-to-Latin spelling, not an English translator. */
object KannadaRomanizer {
    private val consonants = mapOf(
        'ಕ' to "k", 'ಖ' to "kh", 'ಗ' to "g", 'ಘ' to "gh", 'ಙ' to "ng",
        'ಚ' to "ch", 'ಛ' to "chh", 'ಜ' to "j", 'ಝ' to "jh", 'ಞ' to "ny",
        'ಟ' to "t", 'ಠ' to "th", 'ಡ' to "d", 'ಢ' to "dh", 'ಣ' to "n",
        'ತ' to "t", 'ಥ' to "th", 'ದ' to "d", 'ಧ' to "dh", 'ನ' to "n",
        'ಪ' to "p", 'ಫ' to "ph", 'ಬ' to "b", 'ಭ' to "bh", 'ಮ' to "m",
        'ಯ' to "y", 'ರ' to "r", 'ಱ' to "r", 'ಲ' to "l", 'ಳ' to "l",
        'ವ' to "v", 'ಶ' to "sh", 'ಷ' to "sh", 'ಸ' to "s", 'ಹ' to "h", 'ೞ' to "l"
    )
    private val vowels = mapOf(
        'ಅ' to "a", 'ಆ' to "aa", 'ಇ' to "i", 'ಈ' to "ee", 'ಉ' to "u", 'ಊ' to "oo",
        'ಋ' to "ru", 'ೠ' to "roo", 'ಌ' to "lu", 'ೡ' to "loo",
        'ಎ' to "e", 'ಏ' to "ee", 'ಐ' to "ai", 'ಒ' to "o", 'ಓ' to "oo", 'ಔ' to "au"
    )
    private val signs = mapOf(
        'ಾ' to "aa", 'ಿ' to "i", 'ೀ' to "ee", 'ು' to "u", 'ೂ' to "oo",
        'ೃ' to "ru", 'ೄ' to "roo", 'ೢ' to "lu", 'ೣ' to "loo",
        'ೆ' to "e", 'ೇ' to "ee", 'ೈ' to "ai", 'ೊ' to "o", 'ೋ' to "oo", 'ೌ' to "au"
    )

    fun romanize(input: String): String {
        val text = Normalizer.normalize(input, Normalizer.Form.NFC)
        val output = StringBuilder()
        var inherentVowel = false
        text.forEachIndexed { index, character ->
            val consonant = consonants[character]
            val vowel = vowels[character]
            val sign = signs[character]
            when {
                consonant != null -> { output.append(consonant).append('a'); inherentVowel = true }
                sign != null -> {
                    if (inherentVowel) output.setLength(output.length - 1)
                    output.append(sign); inherentVowel = false
                }
                character == '್' -> {
                    if (inherentVowel) output.setLength(output.length - 1)
                    inherentVowel = false
                }
                character == '\u200c' || character == '\u200d' || character == '಼' -> Unit
                else -> {
                    inherentVowel = false
                    when {
                        vowel != null -> output.append(vowel)
                        character == 'ಂ' || character == 'ಁ' -> output.append(when (text.getOrNull(index + 1)) {
                            'ಕ', 'ಖ', 'ಗ', 'ಘ' -> "n"
                            'ಚ', 'ಛ', 'ಜ', 'ಝ', 'ಟ', 'ಠ', 'ಡ', 'ಢ', 'ತ', 'ಥ', 'ದ', 'ಧ', 'ನ' -> "n"
                            else -> "m"
                        })
                        character == 'ಃ' || character == 'ೱ' || character == 'ೲ' -> output.append('h')
                        character in '೦'..'೯' -> output.append(character - '೦')
                        character == 'ಽ' -> output.append('\'')
                        character == '।' || character == '॥' -> output.append('.')
                        character in '\u0c80'..'\u0cff' -> output.append("[?]")
                        else -> output.append(character)
                    }
                }
            }
        }
        return output.toString()
    }
}

/** Partial hypotheses replace each other; only final phrases enter the transcript. */
class CaptionBuffer(private val maxCharacters: Int = 12_000) {
    data class PhraseEntry(val id: Long, val kanglish: String, var english: String, var status: String = "Translating…")

    private val phrases = ArrayDeque<PhraseEntry>()
    private var nextId = 0L
    val entries: List<PhraseEntry> get() = phrases.toList()
    var partial: String = ""
        private set
    var partialEnglish: String = ""
        private set

    val partialDisplay: String
        get() = if (partialEnglish.isNotBlank() && !partialEnglish.equals(partial, ignoreCase = true)) {
            partialEnglish
        } else {
            partial
        }

    val finalized: String
        get() = phrases.joinToString("\n") { entry ->
            if (entry.english.isNotBlank() && !entry.english.equals(entry.kanglish, ignoreCase = true)) {
                entry.english
            } else {
                entry.kanglish
            }
        }

    val finalizedEnglish: String
        get() = phrases.joinToString("\n") { entry ->
            if (entry.english.isNotBlank()) entry.english else entry.kanglish
        }

    fun updatePartial(text: String, english: String = "") {
        partial = KannadaRomanizer.romanize(text.take(maxCharacters)).take(maxCharacters).trim()
        partialEnglish = english.trim()
    }

    fun finalizePhrase(text: String, english: String = ""): Long {
        clearPartial()
        val kanglish = KannadaRomanizer.romanize(text.take(maxCharacters)).take(maxCharacters).trim()
        val eng = english.trim()
        val id = ++nextId
        if (kanglish.isNotEmpty() || eng.isNotEmpty()) {
            phrases.addLast(PhraseEntry(id, kanglish, eng))
        }
        trimHistory()
        return id
    }

    fun updatePhraseEnglish(id: Long, newEnglish: String): Boolean {
        val entry = phrases.find { it.id == id } ?: return false
        val clean = newEnglish.trim().take(maxCharacters)
        if (clean.isNotEmpty()) {
            entry.english = clean
            entry.status = ""
            trimHistory()
            return true
        }
        return false
    }

    fun setStatus(id: Long, status: String): Boolean {
        val entry = phrases.find { it.id == id } ?: return false
        entry.status = status
        return true
    }

    private fun trimHistory() {
        while (phrases.size > 1 && phrases.sumOf { it.kanglish.length + it.english.length + 1 } > maxCharacters) phrases.removeFirst()
    }

    fun clearPartial() {
        partial = ""
        partialEnglish = ""
    }

    fun clear() {
        phrases.clear()
        clearPartial()
    }
}
