package org.kanglish.app.data

import android.content.Context
import org.json.JSONArray

import org.json.JSONObject
import java.io.File
import java.util.Locale

class GlossaryManager(private val context: Context) {

    companion object {
        @Volatile private var instance: GlossaryManager? = null
        fun shared(context: Context): GlossaryManager = instance ?: synchronized(this) {
            instance ?: GlossaryManager(context.applicationContext).also { instance = it }
        }
    }

    private val entries = mutableListOf<Pair<String, String>>()
    private val learnedFile: File get() = File(context.filesDir, "learned_glossary.json")

    init {
        loadBaseGlossary()
        loadLearnedGlossary()
    }

    private fun loadBaseGlossary() {
        try {
            val jsonString = context.assets.open("glossary.json").bufferedReader().use { it.readText() }
            val array = JSONArray(jsonString)
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                val k = obj.getString("kanglish").trim()
                val e = obj.getString("english").trim()
                if (k.isNotEmpty() && e.isNotEmpty()) {
                    entries.add(Pair(k, e))
                }
            }
            entries.sortByDescending { it.first.length }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun loadLearnedGlossary() {
        if (!learnedFile.exists()) return
        try {
            val array = JSONArray(learnedFile.readText(Charsets.UTF_8))
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                val k = obj.optString("kanglish", "").trim()
                val e = obj.optString("english", "").trim()
                if (k.isNotEmpty() && e.isNotEmpty()) {
                    entries.removeAll { it.first.equals(k, ignoreCase = true) }
                    entries.add(Pair(k, e))
                }
            }
            entries.sortByDescending { it.first.length }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    @Synchronized
    fun addLearnedTerm(kanglish: String, english: String) {
        val k = kanglish.trim()
        val e = english.trim()
        if (k.isEmpty() || e.isEmpty()) return

        entries.removeAll { it.first.equals(k, ignoreCase = true) }
        entries.add(Pair(k, e))
        entries.sortByDescending { it.first.length }

        try {
            val array = if (learnedFile.exists()) {
                try { JSONArray(learnedFile.readText(Charsets.UTF_8)) } catch (_: Exception) { JSONArray() }
            } else {
                JSONArray()
            }
            val newObj = JSONObject().apply {
                put("kanglish", k)
                put("english", e)
                put("timestamp", System.currentTimeMillis())
            }
            array.put(newObj)
            learnedFile.writeText(array.toString(2), Charsets.UTF_8)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }


    @Synchronized
    fun getEntries(): List<Pair<String, String>> = entries.toList()

    @Synchronized
    fun findMatches(text: String): List<Pair<String, String>> {
        val lower = text.lowercase(Locale.ROOT)
        val normalized = normalizeText(lower)
        val matches = mutableListOf<Pair<String, String>>()
        val seen = mutableSetOf<String>()

        // 1. Direct and multi-word phrase matching on raw and normalized text
        for ((kanglish, english) in entries) {
            val kLower = kanglish.lowercase(Locale.ROOT)
            val pattern = "\\b${Regex.escape(kLower)}\\b".toRegex()

            if (pattern.containsMatchIn(lower) || pattern.containsMatchIn(normalized)) {
                if (english !in seen) {
                    matches.add(Pair(kanglish, english))
                    seen.add(english)
                }
            }
        }

        // 2. Token-level fuzzy tolerance (Levenshtein distance <= 1 for words >= 5 chars)
        val inputTokens = lower.split(Regex("[^a-zA-Z]+")).filter { it.length >= 4 }
        for (token in inputTokens) {
            val normToken = normalizeText(token)
            for ((kanglish, english) in entries) {
                if (!kanglish.contains(" ")) {
                    val kLower = kanglish.lowercase(Locale.ROOT)
                    val normK = normalizeText(kLower)
                    if (normToken == normK || (normToken.length >= 5 && levenshteinDistance(normToken, normK) <= 1)) {
                        if (english !in seen) {
                            matches.add(Pair(kanglish, english))
                            seen.add(english)
                        }
                    }
                }
            }
        }

        return matches
    }

    private fun normalizeText(input: String): String {
        // Collapses 2+ repeated characters: e.g. "muchooo" -> "mucho", "thikka" -> "thika"
        return input.replace(Regex("([a-z])\\1+"), "$1")
    }

    private fun levenshteinDistance(s1: String, s2: String): Int {
        val dp = Array(s1.length + 1) { IntArray(s2.length + 1) }
        for (i in 0..s1.length) dp[i][0] = i
        for (j in 0..s2.length) dp[0][j] = j
        for (i in 1..s1.length) {
            for (j in 1..s2.length) {
                val cost = if (s1[i - 1] == s2[j - 1]) 0 else 1
                dp[i][j] = minOf(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + cost
                )
            }
        }
        return dp[s1.length][s2.length]
    }

    fun buildGlossaryPromptSnippet(matches: List<Pair<String, String>>): String {
        if (matches.isEmpty()) return ""
        val builder = StringBuilder("Glossary Reference:\n")
        for ((k, e) in matches) {
            builder.append("- \"").append(k).append("\" means \"").append(e).append("\"\n")
        }
        return builder.toString()
    }
}
