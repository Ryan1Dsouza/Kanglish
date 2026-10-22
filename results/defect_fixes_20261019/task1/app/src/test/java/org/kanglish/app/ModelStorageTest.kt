package org.kanglish.app

import android.net.Uri
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.kanglish.app.data.ChatMessage
import org.kanglish.app.inference.TranslationService
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class ModelStorageTest {
    @Test fun rejectedImportPreservesExistingFile() = runBlocking {
        val app = RuntimeEnvironment.getApplication()
        val existing = File(app.filesDir, "active_model.gguf").apply { writeText("existing model placeholder") }
        val invalid = File(app.cacheDir, "not-a-model.txt").apply { writeText("invalid") }
        val result = runCatching { TranslationService(app).importModel(Uri.fromFile(invalid)) }
        assertTrue(result.exceptionOrNull() is IllegalArgumentException)
        assertEquals("existing model placeholder", existing.readText())
        assertFalse(File(app.filesDir, "importing_model.gguf").exists())
    }

    @Test fun savedPhraseWorksWithoutNativeModelAndIsSharedAcrossEntryPoints() = runBlocking {
        val app = RuntimeEnvironment.getApplication()
        val first = TranslationService(app)
        val second = TranslationService(app)
        first.teachModel("test phrase placeholder", "saved placeholder")
        val message = ChatMessage("test", "Tester", "", "test phrase placeholder")
        assertEquals("saved placeholder", second.translateMessage(message))
        assertFalse(second.isLlamaLoaded())
    }
}
