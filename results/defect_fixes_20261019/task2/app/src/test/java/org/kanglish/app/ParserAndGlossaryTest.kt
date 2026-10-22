package org.kanglish.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.kanglish.app.data.WhatsAppParser

class ParserAndGlossaryTest {

    @Test
    fun testWhatsAppParserStandardFormat() {
        val chat = """
            18/10/2026, 10:15 - Ramesh: Hey guru scene enu ivattu?
            18/10/2026, 10:16 - You: oota aaytha modlu?
            18/10/2026, 10:17 - Ramesh: houdu aaitu, swalpa kelsa ide
        """.trimIndent()

        val messages = WhatsAppParser.parse(chat)
        assertEquals(3, messages.size)
        assertEquals("Ramesh", messages[0].sender)
        assertEquals("Hey guru scene enu ivattu?", messages[0].originalText)
        assertEquals("You", messages[1].sender)
        assertEquals("oota aaytha modlu?", messages[1].originalText)
        assertEquals("Ramesh", messages[2].sender)
        assertEquals("houdu aaitu, swalpa kelsa ide", messages[2].originalText)
    }

    @Test
    fun testWhatsAppParserBracketFormat() {
        val chat = """
            [18/10/26, 10:15:30] Ramesh: naale movie hogtiya?
            [18/10/26, 10:16:00] You: bekagilla bro, tumba busy idini
        """.trimIndent()

        val messages = WhatsAppParser.parse(chat)
        assertEquals(2, messages.size)
        assertEquals("Ramesh", messages[0].sender)
        assertEquals("naale movie hogtiya?", messages[0].originalText)
        assertEquals("You", messages[1].sender)
        assertEquals("bekagilla bro, tumba busy idini", messages[1].originalText)
    }

    @Test
    fun testWhatsAppParserRawLines() {
        val raw = """
            guru scene enu
            oota aaytha
        """.trimIndent()

        val messages = WhatsAppParser.parse(raw)
        assertEquals(2, messages.size)
        assertEquals("guru scene enu", messages[0].originalText)
        assertEquals("oota aaytha", messages[1].originalText)
    }
}
