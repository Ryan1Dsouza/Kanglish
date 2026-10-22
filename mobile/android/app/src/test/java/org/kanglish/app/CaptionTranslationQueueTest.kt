package org.kanglish.app

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import org.kanglish.app.audio.CaptionTranslationQueue

class CaptionTranslationQueueTest {
    @Test fun slowRequestsStayBoundedAndStalePendingPhrasesAreSkipped() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        var active = 0
        var peak = 0
        val completed = mutableListOf<Long>()
        val skipped = mutableListOf<Long>()
        val queue = CaptionTranslationQueue(this, {
            active++; peak = maxOf(peak, active)
            try { gate.await(); "result" } finally { active-- }
        }, { id, _ -> completed += id }, { skipped += it })
        repeat(10) { queue.submit(it.toLong(), "source") }
        yield()
        assertEquals(2, active)
        assertEquals(listOf(2L, 3L, 4L, 5L, 6L), skipped)
        gate.complete(Unit)
        while (completed.size < 5) yield()
        assertTrue(peak <= 2)
        assertEquals(setOf(0L, 1L, 7L, 8L, 9L), completed.toSet())
        queue.clear()
    }

    @Test fun clearingPreventsLateResultsAndNewPhrasesStillTranslate() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        val results = mutableListOf<Long>()
        val queue = CaptionTranslationQueue(this, { if (it == "old") gate.await(); "result" }, { id, _ -> results += id }, {})
        queue.submit(1L, "old")
        yield()
        queue.clear()
        queue.submit(2L, "new")
        gate.complete(Unit)
        while (2L !in results) yield()
        assertEquals(listOf(2L), results)
        queue.clear()
    }
}
