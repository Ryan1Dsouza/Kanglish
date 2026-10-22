package org.kanglish.app.audio

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/** Called on the UI thread. A slow translator cannot grow an unbounded caption backlog. */
class CaptionTranslationQueue(
    private val scope: CoroutineScope,
    private val translate: suspend (String) -> String?,
    private val completed: (Long, String?) -> Unit,
    private val skipped: (Long) -> Unit,
    private val concurrency: Int = 2,
    private val capacity: Int = 3
) {
    private data class Work(val id: Long, val text: String, val generation: Int)
    private val pending = ArrayDeque<Work>()
    private val jobs = mutableSetOf<Job>()
    private var active = 0
    private var generation = 0

    fun submit(id: Long, text: String) {
        if (pending.size >= capacity) skipped(pending.removeFirst().id)
        pending.addLast(Work(id, text, generation))
        pump()
    }

    private fun pump() {
        while (active < concurrency && pending.isNotEmpty()) {
            val work = pending.removeFirst()
            active++
            val job = scope.launch {
                try {
                    val result = try { translate(work.text) } catch (e: CancellationException) { throw e } catch (_: Exception) { null }
                    if (work.generation == generation) completed(work.id, result)
                } finally {
                    active--
                    pump()
                }
            }
            jobs.add(job)
            job.invokeOnCompletion { jobs.remove(job) }
        }
    }

    fun clear() {
        generation++
        pending.clear()
        jobs.toList().forEach { it.cancel() }
    }
}
