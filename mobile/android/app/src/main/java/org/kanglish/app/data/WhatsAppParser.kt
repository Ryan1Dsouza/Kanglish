package org.kanglish.app.data

import java.util.UUID
import java.util.regex.Pattern

object WhatsAppParser {

    // Regex 1: 18/10/2026, 10:15 - Ramesh: Message
    // Regex 2: [18/10/26, 10:15:30] Ramesh: Message
    // Regex 3: 10/18/26, 10:15 AM - Ramesh: Message
    private val PATTERN_STANDARD = Pattern.compile(
        "^\\s*(?:\\[)?(\\d{1,2}[/.-]\\d{1,2}[/.-]\\d{2,4},\\s+\\d{1,2}:\\d{2}(?::\\d{2})?(?:\\s+[APMapm]{2})?)(?:\\])?(?:\\s+-\\s+|\\s+)([^:]+):\\s+(.*)$"
    )

    fun parse(text: String): List<ChatMessage> {
        val messages = mutableListOf<ChatMessage>()
        val lines = text.lines()

        var currentSender: String? = null
        var currentTimestamp: String? = null
        val currentBody = StringBuilder()

        fun flush() {
            if (currentSender != null && currentBody.isNotBlank()) {
                val body = currentBody.toString().trim()
                if (!body.contains("Messages and calls are end-to-end encrypted") &&
                    !body.contains("<Media omitted>")
                ) {
                    messages.add(
                        ChatMessage(
                            id = UUID.randomUUID().toString(),
                            sender = currentSender!!,
                            timestamp = currentTimestamp ?: "",
                            originalText = body
                        )
                    )
                }
            }
            currentBody.clear()
        }

        for (line in lines) {
            val matcher = PATTERN_STANDARD.matcher(line)
            if (matcher.matches()) {
                flush()
                currentTimestamp = matcher.group(1)?.trim() ?: ""
                currentSender = matcher.group(2)?.trim() ?: "Unknown"
                currentBody.append(matcher.group(3) ?: "")
            } else if (line.isNotBlank()) {
                if (currentSender != null) {
                    currentBody.append("\n").append(line)
                } else {
                    // Plain line without WhatsApp header: treat as direct message
                    messages.add(
                        ChatMessage(
                            id = UUID.randomUUID().toString(),
                            sender = "Message ${messages.size + 1}",
                            timestamp = "",
                            originalText = line.trim()
                        )
                    )
                }
            }
        }
        flush()

        return messages
    }
}
