package org.kanglish.app

import org.junit.Assert.*
import org.junit.Test
import org.kanglish.app.audio.CaptionBuffer
import org.kanglish.app.audio.KannadaRomanizer

class KannadaCaptionsTest {
    @Test fun preservesNegativeAndTimeWordsInsteadOfTranslatingTheirMeaning() {
        assertEquals("naanu baralla ivattu", KannadaRomanizer.romanize("ನಾನು ಬರಲ್ಲ ಇವತ್ತು"))
        assertEquals("naale college ge barteeraa?", KannadaRomanizer.romanize("ನಾಳೆ college ಗೆ ಬರ್ತೀರಾ?"))
    }
    @Test fun handlesVowelSignsConjunctsDigitsAndCodeSwitching() {
        assertEquals("kannada 123, meeting 5 PM!", KannadaRomanizer.romanize("ಕನ್ನಡ ೧೨೩, meeting 5 PM!"))
        assertEquals("namaskaara", KannadaRomanizer.romanize("ನಮಸ್ಕಾರ"))
        assertEquals("bengalooru", KannadaRomanizer.romanize("ಬೆಂಗಳೂರು"))
        assertEquals("shree", KannadaRomanizer.romanize("ಶ್ರೀ"))
        assertEquals("ksha", KannadaRomanizer.romanize("ಕ್\u200dಷ"))
        assertEquals(KannadaRomanizer.romanize("ಕೋ"), KannadaRomanizer.romanize("ಕ\u0cc6\u0cc2\u0cd5"))
    }
    @Test fun partialRevisionsDoNotDuplicateAndFinalWordsReplaceThem() {
        val buffer = CaptionBuffer()
        buffer.updatePartial("ನಾನು")
        buffer.updatePartial("ನಾನು ಬರಲ್ಲ")
        assertEquals("", buffer.finalized)
        assertEquals("naanu baralla", buffer.partial)
        buffer.finalizePhrase("ನಾನು ಬರಲ್ಲ ಇವತ್ತು")
        assertEquals("naanu baralla ivattu", buffer.finalized)
        assertEquals("", buffer.partial)
        buffer.finalizePhrase("ನಾಳೆ")
        assertEquals("naanu baralla ivattu\nnaale", buffer.finalized)
        buffer.clear()
        assertEquals("", buffer.finalized)
    }
    @Test fun genuinelyRepeatedPhrasesRemainAndOldTranscriptIsBounded() {
        val buffer = CaptionBuffer(15)
        repeat(2) { buffer.finalizePhrase("ಹಾಯ್") }
        assertEquals("haay\nhaay", buffer.finalized)
        repeat(100) { buffer.finalizePhrase("ಹಾಯ್") }
        assertTrue(buffer.finalized.length <= 15)
    }
}
