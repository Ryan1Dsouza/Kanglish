#include <jni.h>
#include <android/log.h>
#include <string>
#include <vector>
#include <mutex>
#include <algorithm>
#include <unistd.h>

#include "llama.h"

#define TAG "KanglishLlama"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

static std::mutex g_mutex;
static llama_model   * g_model   = nullptr;
static llama_context * g_ctx     = nullptr;
static llama_sampler * g_sampler = nullptr;

static void clean_up_resources() {
    if (g_sampler) {
        llama_sampler_free(g_sampler);
        g_sampler = nullptr;
    }
    if (g_ctx) {
        llama_free(g_ctx);
        g_ctx = nullptr;
    }
    if (g_model) {
        llama_model_free(g_model);
        g_model = nullptr;
    }
}

static jbyteArray java_bytes(JNIEnv *env, const std::string &text) {
    jbyteArray result = env->NewByteArray(static_cast<jsize>(text.size()));
    if (result && !text.empty()) {
        env->SetByteArrayRegion(result, 0, static_cast<jsize>(text.size()), reinterpret_cast<const jbyte *>(text.data()));
    }
    return result;
}

extern "C" {

JNIEXPORT jboolean JNICALL
Java_org_kanglish_app_inference_LlamaNativeBridge_nativeInit(
        JNIEnv *env, jclass /*clazz*/, jstring /*nativeLibDir*/) {
    std::lock_guard<std::mutex> lock(g_mutex);
    LOGI("Initializing llama backend...");
    llama_backend_init();
    return JNI_TRUE;
}

JNIEXPORT jboolean JNICALL
Java_org_kanglish_app_inference_LlamaNativeBridge_nativeLoadModel(
        JNIEnv *env, jclass /*clazz*/, jstring modelPath) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!modelPath) {
        LOGE("modelPath is null");
        return JNI_FALSE;
    }

    const char *path_chars = env->GetStringUTFChars(modelPath, nullptr);
    if (!path_chars) return JNI_FALSE;

    std::string path_str(path_chars);
    env->ReleaseStringUTFChars(modelPath, path_chars);

    LOGI("Loading model from: %s", path_str.c_str());
    clean_up_resources();

    llama_model_params mparams = llama_model_default_params();
    g_model = llama_model_load_from_file(path_str.c_str(), mparams);
    if (!g_model) {
        LOGE("Failed to load model from %s", path_str.c_str());
        return JNI_FALSE;
    }

    llama_context_params cparams = llama_context_default_params();
    int n_threads = std::max(4, std::min(6, (int)sysconf(_SC_NPROCESSORS_ONLN) - 2));
    cparams.n_threads = n_threads;
    cparams.n_threads_batch = n_threads;
    cparams.n_ctx = 1024;
    cparams.n_batch = 512;

    g_ctx = llama_init_from_model(g_model, cparams);
    if (!g_ctx) {
        LOGE("Failed to create context from model");
        llama_model_free(g_model);
        g_model = nullptr;
        return JNI_FALSE;
    }

    auto sparams = llama_sampler_chain_default_params();
    g_sampler = llama_sampler_chain_init(sparams);
    llama_sampler_chain_add(g_sampler, llama_sampler_init_temp(0.1f));
    llama_sampler_chain_add(g_sampler, llama_sampler_init_dist(42));

    LOGI("Model loaded successfully with %d threads, n_ctx=1024", n_threads);
    return JNI_TRUE;
}

JNIEXPORT void JNICALL
Java_org_kanglish_app_inference_LlamaNativeBridge_nativeUnloadModel(
        JNIEnv *env, jclass /*clazz*/) {
    std::lock_guard<std::mutex> lock(g_mutex);
    LOGI("Unloading model...");
    clean_up_resources();
}

JNIEXPORT jboolean JNICALL
Java_org_kanglish_app_inference_LlamaNativeBridge_nativeIsLoaded(
        JNIEnv *env, jclass /*clazz*/) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_model != nullptr && g_ctx != nullptr) ? JNI_TRUE : JNI_FALSE;
}

JNIEXPORT jbyteArray JNICALL
Java_org_kanglish_app_inference_LlamaNativeBridge_nativeTranslate(
        JNIEnv *env, jclass /*clazz*/, jbyteArray prompt, jint maxTokens) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_model || !g_ctx || !g_sampler) {
        LOGE("Model not loaded");
        return java_bytes(env, "[Error: Model not loaded]");
    }

    if (!prompt) return java_bytes(env, "[Error: Invalid message]");
    std::string prompt_str(env->GetArrayLength(prompt), '\0');
    env->GetByteArrayRegion(prompt, 0, static_cast<jsize>(prompt_str.size()), reinterpret_cast<jbyte *>(prompt_str.data()));
    if (env->ExceptionCheck()) return nullptr;

    const struct llama_vocab * vocab = llama_model_get_vocab(g_model);

    // Tokenize
    int n_prompt_max = prompt_str.length() + 256;
    std::vector<llama_token> tokens(n_prompt_max);
    int n_tokens = llama_tokenize(vocab, prompt_str.c_str(), prompt_str.length(),
                                  tokens.data(), n_prompt_max, true, true);
    if (n_tokens < 0) {
        tokens.resize(-n_tokens);
        n_tokens = llama_tokenize(vocab, prompt_str.c_str(), prompt_str.length(),
                                  tokens.data(), tokens.size(), true, true);
    }
    if (n_tokens < 0) return java_bytes(env, "[Error: Could not tokenize message]");
    tokens.resize(n_tokens);

    if (tokens.empty()) {
        return java_bytes(env, "");
    }

    // Reset KV cache and sampler
    llama_memory_clear(llama_get_memory(g_ctx), false);
    llama_sampler_reset(g_sampler);

    const int limit = std::min(maxTokens > 0 ? maxTokens : 192, 192);
    if (n_tokens + limit > static_cast<int>(llama_n_ctx(g_ctx))) {
        return java_bytes(env, "[Error: Message and context are too long for this model. Translate a shorter selection.]");
    }

    // Prefill in batches; imported chat context can exceed n_batch.
    llama_batch batch;
    const int batch_size = static_cast<int>(llama_n_batch(g_ctx));
    for (int offset = 0; offset < n_tokens; offset += batch_size) {
        batch = llama_batch_get_one(tokens.data() + offset, std::min(batch_size, n_tokens - offset));
        if (llama_decode(g_ctx, batch) != 0) {
            return java_bytes(env, "[Error: Could not process message. Try a shorter selection.]");
        }
    }

    std::string output;
    bool completed = false;
    for (int i = 0; i < limit; ++i) {
        llama_token id = llama_sampler_sample(g_sampler, g_ctx, -1);
        if (llama_vocab_is_eog(vocab, id)) {
            completed = true;
            break;
        }

        std::vector<char> piece(128);
        int n_piece = llama_token_to_piece(vocab, id, piece.data(), piece.size(), 0, false);
        if (n_piece < 0) {
            piece.resize(-n_piece);
            n_piece = llama_token_to_piece(vocab, id, piece.data(), piece.size(), 0, false);
        }
        if (n_piece > 0) output.append(piece.data(), n_piece);

        llama_sampler_accept(g_sampler, id);
        batch = llama_batch_get_one(&id, 1);
        if (llama_decode(g_ctx, batch) != 0) {
            return java_bytes(env, "[Error: Translation stopped unexpectedly. Try a shorter message.]");
        }
    }

    if (!completed) return java_bytes(env, "[Error: Translation reached the output limit. Try a shorter message.]");
    return java_bytes(env, output);
}

} // extern "C"
