package org.kanglish.app.inference

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class TeacherResult(
    val success: Boolean,
    val isMatch: Boolean,
    val teacherTranslation: String,
    val explanation: String = ""
)

class TeacherService(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("teacher_prefs", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_GEMINI = "pref_gemini_key"
        private const val KEY_GROQ = "pref_groq_key"
        private const val KEY_ENABLED = "pref_teacher_enabled_explicit_v2"

    }

    var geminiKey: String
        get() = prefs.getString(KEY_GEMINI, "") ?: ""
        set(value) = prefs.edit().putString(KEY_GEMINI, value.trim()).apply()

    var groqKey: String
        get() = prefs.getString(KEY_GROQ, "") ?: ""
        set(value) = prefs.edit().putString(KEY_GROQ, value.trim()).apply()

    var isTeacherEnabled: Boolean
        get() = prefs.getBoolean(KEY_ENABLED, false)
        set(value) = prefs.edit().putBoolean(KEY_ENABLED, value).apply()

    suspend fun verifyTranslation(
        kanglish: String,
        studentTranslation: String
    ): TeacherResult = withContext(Dispatchers.IO) {
        if (!isTeacherEnabled || kanglish.isBlank()) {
            return@withContext TeacherResult(success = false, isMatch = true, teacherTranslation = "")
        }

        // Try Gemini first
        val geminiResult = callGemini(kanglish, studentTranslation)
        if (geminiResult != null) {
            return@withContext geminiResult
        }

        // Fallback to Groq
        val groqResult = callGroq(kanglish, studentTranslation)
        if (groqResult != null) {
            return@withContext groqResult
        }

        TeacherResult(success = false, isMatch = true, teacherTranslation = "")
    }

    private fun callGemini(kanglish: String, studentTranslation: String): TeacherResult? {
        val key = geminiKey
        if (key.isBlank()) return null

        return try {
            val endpoint =
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key=$key"
            val prompt = """
                You are an expert Kannada & Kanglish translator evaluating a student translation.
                Original Kanglish: "$kanglish"
                Student English: "$studentTranslation"

                Analyze if the student captured the natural, colloquial meaning.
                Return raw JSON:
                {
                  "isMatch": true/false,
                  "teacherTranslation": "natural English translation",
                  "explanation": "brief note if mismatch"
                }
            """.trimIndent()

            val body = JSONObject().apply {
                val partsArray = JSONArray().put(JSONObject().put("text", prompt))
                put("contents", JSONArray().put(JSONObject().put("parts", partsArray)))
                put("generationConfig", JSONObject().apply {
                    put("responseMimeType", "application/json")
                })
            }

            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                doOutput = true
                connectTimeout = 8000
                readTimeout = 8000
            }

            OutputStreamWriter(conn.outputStream, "UTF-8").use { it.write(body.toString()) }

            if (conn.responseCode == 200) {
                val responseText = conn.inputStream.bufferedReader().use { it.readText() }
                val root = JSONObject(responseText)
                val text = root.getJSONArray("candidates")
                    .getJSONObject(0)
                    .getJSONObject("content")
                    .getJSONArray("parts")
                    .getJSONObject(0)
                    .getString("text")

                parseTeacherJson(text, studentTranslation)
            } else {
                null
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun callGroq(kanglish: String, studentTranslation: String): TeacherResult? {
        val key = groqKey
        if (key.isBlank()) return null

        return try {
            val endpoint = "https://api.groq.com/openai/v1/chat/completions"
            val prompt = """
                Original Kanglish: "$kanglish"
                Student English: "$studentTranslation"
                Evaluate if the student translation is accurate.
                Return JSON with keys: isMatch (boolean), teacherTranslation (string), explanation (string).
            """.trimIndent()

            val body = JSONObject().apply {
                put("model", "qwen/qwen3.8-27b")
                put("messages", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "system")
                        put("content", "You evaluate Kanglish translations. Output only valid JSON.")
                    })
                    put(JSONObject().apply {
                        put("role", "user")
                        put("content", prompt)
                    })
                })
                put("response_format", JSONObject().put("type", "json_object"))
            }

            val conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Authorization", "Bearer $key")
                doOutput = true
                connectTimeout = 8000
                readTimeout = 8000
            }

            OutputStreamWriter(conn.outputStream, "UTF-8").use { it.write(body.toString()) }

            if (conn.responseCode == 200) {
                val responseText = conn.inputStream.bufferedReader().use { it.readText() }
                val root = JSONObject(responseText)
                val content = root.getJSONArray("choices")
                    .getJSONObject(0)
                    .getJSONObject("message")
                    .getString("content")

                parseTeacherJson(content, studentTranslation)
            } else {
                null
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun parseTeacherJson(raw: String, fallback: String): TeacherResult? {
        return try {
            var clean = raw.trim()
            clean = clean.replace(Regex("^```json\\s*", RegexOption.IGNORE_CASE), "")
            clean = clean.replace(Regex("^```\\s*"), "")
            clean = clean.replace(Regex("\\s*```$"), "")
            val start = clean.indexOf('{')
            val end = clean.lastIndexOf('}')
            if (start != -1 && end != -1 && end > start) {
                clean = clean.substring(start, end + 1)
            }
            val json = JSONObject(clean)
            TeacherResult(
                success = true,
                isMatch = json.optBoolean("isMatch", true),
                teacherTranslation = json.optString("teacherTranslation", fallback).trim(),
                explanation = json.optString("explanation", "")
            )
        } catch (_: Exception) {
            null
        }
    }
}
