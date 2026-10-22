package org.kanglish.app.inference

import android.content.Context
import android.util.Log

object LlamaNativeBridge {
    private const val TAG = "LlamaNativeBridge"
    private var isLibraryLoaded = false
    @Volatile private var modelLoaded = false
    private var initialized = false

    init {
        try {
            System.loadLibrary("kanglish_llama")
            isLibraryLoaded = true
            Log.i(TAG, "libkanglish_llama.so loaded successfully")
        } catch (e: UnsatisfiedLinkError) {
            Log.e(TAG, "Failed to load libkanglish_llama.so: ${e.message}")
            isLibraryLoaded = false
        }
    }

    fun isNativeAvailable(): Boolean = isLibraryLoaded

    fun initialize(context: Context): Boolean {
        if (!isLibraryLoaded) return false
        if (initialized) return true
        return try {
            nativeInit(context.applicationInfo.nativeLibraryDir).also { initialized = it }
        } catch (e: Exception) {
            Log.e(TAG, "nativeInit error: ${e.message}")
            false
        }
    }

    fun loadModel(path: String): Boolean {
        if (!isLibraryLoaded) return false
        return try {
            nativeLoadModel(path).also { modelLoaded = it }
        } catch (e: Exception) {
            modelLoaded = false
            Log.e(TAG, "nativeLoadModel error: ${e.message}")
            false
        }
    }

    fun unloadModel() {
        if (!isLibraryLoaded) return
        try {
            nativeUnloadModel()
            modelLoaded = false
        } catch (e: Exception) {
            Log.e(TAG, "nativeUnloadModel error: ${e.message}")
        }
    }

    fun isModelLoaded(): Boolean = modelLoaded

    fun translate(prompt: String, maxTokens: Int = 256): String {
        if (!isLibraryLoaded) return "[Error: Native library unavailable]"
        return try {
            nativeTranslate(prompt.toByteArray(Charsets.UTF_8), maxTokens).toString(Charsets.UTF_8)
        } catch (e: Exception) {
            Log.e(TAG, "nativeTranslate error: ${e.message}")
            "[Error: ${e.message}]"
        }
    }

    private external fun nativeInit(nativeLibDir: String): Boolean
    private external fun nativeLoadModel(modelPath: String): Boolean
    private external fun nativeUnloadModel()
    private external fun nativeIsLoaded(): Boolean
    private external fun nativeTranslate(prompt: ByteArray, maxTokens: Int): ByteArray
}
