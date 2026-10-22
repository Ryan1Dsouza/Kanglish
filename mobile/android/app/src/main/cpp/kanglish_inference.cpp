#include <jni.h>
#include <android/log.h>
#include <string>
#include <vector>
#include <mutex>
#include <algorithm>
#include <cstring>
#include <unistd.h>

#include "llama.h"

#define TAG "KanglishLlama"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

static const std::string SYSTEM_PROMPT =
    "<|im_start|>system\n"
    "You are an expert translator for Coastal Karnataka languages (Kannada, Tulu, Konkani, Kanglish). "
    "Translate the user's Romanized input into natural, accurate English. Output only the English translation.<|im_end|>\n";

static std::string build_user_turn(const std::string& raw_input) {
    // If input already contains ChatML user tags, extract just the inner user message
    size_t u_pos = raw_input.find("<|im_start|>user\n");
    if (u_pos != std::string::npos) {
        size_t u_content_start = u_pos + 16;
        size_t u_end = raw_input.find("<|im_end|>", u_content_start);
        std::string user_content = (u_end != std::string::npos)
            ? raw_input.substr(u_content_start, u_end - u_content_start)
            : raw_input.substr(u_content_start);
        return "<|im_start|>user\n" + user_content + "<|im_end|>\n<|im_start|>assistant\n";
    }
    return "<|im_start|>user\n" + raw_input + "<|im_end|>\n<|im_start|>assistant\n";
}

// Memory sequence removal wrapper compatible with llama.cpp memory API
static inline bool llama_kv_cache_seq_rm(llama_context * ctx, llama_seq_id seq_id, llama_pos p0, llama_pos p1) {
    return llama_memory_seq_rm(llama_get_memory(ctx), seq_id, p0, p1);
}

static std::mutex g_mutex;
static llama_model   * g_model   = nullptr;
static llama_context * g_ctx     = nullptr;
static int g_n_past_system       = 0;

static void clean_up_resources() {
    g_n_past_system = 0;
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
    cparams.n_ctx = 512;
    cparams.n_batch = 512;
    cparams.n_threads = 4;
    cparams.n_threads_batch = 4;

    g_ctx = llama_init_from_model(g_model, cparams);
    if (!g_ctx) {
        LOGE("Failed to create context from model");
        llama_model_free(g_model);
        g_model = nullptr;
        return JNI_FALSE;
    }

    // Pre-evaluate and cache the system prompt tokens into KV cache
    const struct llama_vocab * vocab = llama_model_get_vocab(g_model);
    int n_system_max = SYSTEM_PROMPT.length() + 64;
    std::vector<llama_token> system_tokens(n_system_max);
    int n_tokens = llama_tokenize(vocab, SYSTEM_PROMPT.c_str(), SYSTEM_PROMPT.length(),
                                  system_tokens.data(), n_system_max, true, true);
    if (n_tokens < 0) {
        system_tokens.resize(-n_tokens);
        n_tokens = llama_tokenize(vocab, SYSTEM_PROMPT.c_str(), SYSTEM_PROMPT.length(),
                                  system_tokens.data(), system_tokens.size(), true, true);
    }

    if (n_tokens > 0) {
        system_tokens.resize(n_tokens);
        llama_batch batch = llama_batch_get_one(system_tokens.data(), n_tokens);
        if (llama_decode(g_ctx, batch) != 0) {
            LOGE("Failed to decode system prompt into KV cache");
            g_n_past_system = 0;
        } else {
            g_n_past_system = n_tokens;
            LOGI("System prompt cached successfully (%d tokens)", g_n_past_system);
        }
    } else {
        LOGW("Failed to tokenize system prompt");
        g_n_past_system = 0;
    }

    LOGI("Model loaded successfully: n_ctx=512, n_batch=512, n_threads=4");
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

    if (!g_model || !g_ctx) {
        LOGE("Model not loaded");
        return java_bytes(env, "[Error: Model not loaded]");
    }

    if (!prompt) return java_bytes(env, "[Error: Invalid message]");
    std::string prompt_str(env->GetArrayLength(prompt), '\0');
    env->GetByteArrayRegion(prompt, 0, static_cast<jsize>(prompt_str.size()), reinterpret_cast<jbyte *>(prompt_str.data()));
    if (env->ExceptionCheck()) return nullptr;

    const struct llama_vocab * vocab = llama_model_get_vocab(g_model);

    // Build strict ChatML user turn: <|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n
    std::string user_turn = build_user_turn(prompt_str);

    // 1. Clear KV cache after cached system prompt tokens (preserves system KV cache)
    llama_kv_cache_seq_rm(g_ctx, 0, g_n_past_system, -1);

    // 2. Tokenize user turn (add_special = false since system prompt has BOS, parse_special = true)
    int n_user_max = user_turn.length() + 128;
    std::vector<llama_token> tokens(n_user_max);
    int n_tokens = llama_tokenize(vocab, user_turn.c_str(), user_turn.length(),
                                  tokens.data(), n_user_max, false, true);
    if (n_tokens < 0) {
        tokens.resize(-n_tokens);
        n_tokens = llama_tokenize(vocab, user_turn.c_str(), user_turn.length(),
                                  tokens.data(), tokens.size(), false, true);
    }
    if (n_tokens <= 0) return java_bytes(env, "[Error: Could not tokenize user input]");
    tokens.resize(n_tokens);

    if (g_n_past_system + n_tokens >= static_cast<int>(llama_n_ctx(g_ctx))) {
        return java_bytes(env, "[Error: Message is too long for this model. Translate a shorter selection.]");
    }

    // Prefill user prompt in batches
    const int batch_size = static_cast<int>(llama_n_batch(g_ctx));
    for (int offset = 0; offset < n_tokens; offset += batch_size) {
        llama_batch batch = llama_batch_get_one(tokens.data() + offset, std::min(batch_size, n_tokens - offset));
        if (llama_decode(g_ctx, batch) != 0) {
            return java_bytes(env, "[Error: Could not process message. Try a shorter selection.]");
        }
    }

    // 3. Greedy sampling & strict EOG stopping for low-latency translation
    llama_sampler * smpl = llama_sampler_init_greedy();
    std::string result;
    const int limit = maxTokens > 0 ? std::min((int)maxTokens, 128) : 128;

    for (int i = 0; i < limit; ++i) {
        llama_token new_token_id = llama_sampler_sample(smpl, g_ctx, -1);
        if (llama_vocab_is_eog(vocab, new_token_id)) {
            break;
        }

        char buf[256];
        int n = llama_token_to_piece(vocab, new_token_id, buf, sizeof(buf), 0, true);
        if (n > 0) {
            std::string piece(buf, n);
            if (piece == "<|im_end|>" || piece == "<|endoftext|>" || piece == "<|im_start|>") {
                break;
            }
            result += piece;
        }

        llama_sampler_accept(smpl, new_token_id);
        llama_batch batch = llama_batch_get_one(&new_token_id, 1);
        if (llama_decode(g_ctx, batch) != 0) {
            break;
        }
    }
    llama_sampler_free(smpl);

    return java_bytes(env, result);
}

} // extern "C"
