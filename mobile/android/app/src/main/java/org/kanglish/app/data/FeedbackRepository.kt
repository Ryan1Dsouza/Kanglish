package org.kanglish.app.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class FeedbackItem(
    val timestamp: String,
    val sender: String,
    val originalText: String,
    val generatedTranslation: String,
    val userCorrection: String
)

class FeedbackRepository(private val context: Context) {

    private val file: File
        get() = File(context.filesDir, "feedback_nuance.json")

    @Synchronized
    fun saveFeedback(
        sender: String,
        originalText: String,
        generatedTranslation: String,
        userCorrection: String
    ) {
        val existing = getAllFeedback().toMutableList()
        val now = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        existing.add(
            FeedbackItem(
                timestamp = now,
                sender = sender,
                originalText = originalText,
                generatedTranslation = generatedTranslation,
                userCorrection = userCorrection
            )
        )

        val array = JSONArray()
        for (item in existing) {
            val obj = JSONObject()
            obj.put("timestamp", item.timestamp)
            obj.put("sender", item.sender)
            obj.put("originalText", item.originalText)
            obj.put("generatedTranslation", item.generatedTranslation)
            obj.put("userCorrection", item.userCorrection)
            array.put(obj)
        }
        file.writeText(array.toString(2), Charsets.UTF_8)
    }

    @Synchronized
    fun getAllFeedback(): List<FeedbackItem> {
        if (!file.exists()) return emptyList()
        return try {
            val content = file.readText(Charsets.UTF_8)
            val array = JSONArray(content)
            val items = mutableListOf<FeedbackItem>()
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                items.add(
                    FeedbackItem(
                        timestamp = obj.optString("timestamp"),
                        sender = obj.optString("sender"),
                        originalText = obj.optString("originalText"),
                        generatedTranslation = obj.optString("generatedTranslation"),
                        userCorrection = obj.optString("userCorrection")
                    )
                )
            }
            items
        } catch (e: Exception) {
            e.printStackTrace()
            emptyList()
        }
    }

    @Synchronized
    fun clearFeedback() {
        if (file.exists()) {
            file.delete()
        }
    }
}
