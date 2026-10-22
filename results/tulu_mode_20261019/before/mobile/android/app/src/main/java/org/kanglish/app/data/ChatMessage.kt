package org.kanglish.app.data

enum class MessageStatus {
    PENDING,
    TRANSLATING,
    TRANSLATED,
    FAILED
}

data class ChatMessage(
    val id: String,
    val sender: String,
    val timestamp: String,
    val originalText: String,
    var translatedText: String = "",
    var status: MessageStatus = MessageStatus.PENDING,
    var matchedGlossaryTerms: List<Pair<String, String>> = emptyList(),
    var isFlaggedWrong: Boolean = false,
    var userCorrection: String = "",
    var isTeacherChecked: Boolean = false,
    var isTeacherMatch: Boolean = true,
    var teacherSuggestion: String = "",
    var isLearned: Boolean = false,
    var isTeacherUncertain: Boolean = false,
    var teacherExplanation: String = "",
    var usedApprovedCorrection: Boolean = false
)

