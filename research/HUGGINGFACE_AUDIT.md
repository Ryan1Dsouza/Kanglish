# Rigorous Hugging Face Repository Audit for `kanglish-foss`

**Audit Date:** 2026-10-18  
**Auditor:** Antigravity / Gemini via Hugging Face MCP  
**HF Authenticated Account:** `@Ryan1Dsouza`  
**Purpose:** Evaluate open models and datasets on the Hugging Face Hub for Romanized Kannada (Kanglish) to English translation, offline compatibility, licensing compliance, and training suitability.

---

## 1. Executive Summary

A critical finding of this audit is that **almost all existing "Kannada-English" translation models and datasets on Hugging Face assume native Kannada script (`kn_Knda`)**, rather than Romanized Kanglish (`kn_Latn`). 

Feeding informal Romanized Kanglish (e.g. *"naale college ge barthira?"*) directly into standard Indic translation models (like `IndicTrans2` or `NLLB-200`) produces immediate tokenization failure or gibberish because their vocabularies and language tags expect Kannada Unicode characters (`U+0C80`–`U+0CFF`).

However, this audit identified two viable technical paths:
1. **Direct Kanglish LLM Normalization / Decoding:** `RakshithFury/qwen3-4b-codemixed-kan-en` is an authentic, purpose-built Kanglish normalizer and translator fine-tuned from Qwen, handling WhatsApp chat idioms and code-mixing directly.
2. **Two-Stage Transliterate + Translate Pipeline:** Using `ai4bharat/IndicXlit` (or the 2.9M-pair `ai4bharat/Aksharantar` Kannada lexicon) to transliterate phonetic Kanglish into canonical Kannada script, followed by translation via `ai4bharat/indictrans2-indic-en-dist-200M` or your existing local Ollama LLMs with glossary injection.

---

## 2. Models Audit

### Model 1: `ai4bharat/indictrans2-indic-en-dist-200M`
- **Repository Link:** [https://hf.co/ai4bharat/indictrans2-indic-en-dist-200M](https://hf.co/ai4bharat/indictrans2-indic-en-dist-200M)
- **Model Type:** Sequence-to-Sequence Machine Translation (`AutoModelForSeq2SeqLM`)
- **Base Architecture:** Custom IndicTrans (Transformer Encoder-Decoder with SentencePiece)
- **Model Size / Files:** 228.3M parameters; `model.safetensors` is 913.4 MB (PyTorch weights also present at 913.5 MB).
- **Format & Ollama Compatibility:** **Incompatible with Ollama.** Ollama only supports autoregressive causal language models via GGUF (e.g. LLaMA, Qwen, Mistral, Gemma). IndicTrans2 is an encoder-decoder model requiring Hugging Face Transformers with `trust_remote_code=True` and `IndicTransToolkit`.
- **Script & Romanization Support:** **Native Kannada script (`kan_Knda`) only.** Inspection of `tokenization_indictrans.py` confirms that `LANGUAGE_TAGS` contains `kan_Knda` and `eng_Latn`. There is **no** `kan_Latn` tag. Romanized Kannada cannot be passed directly as input.
- **Colloquial & Code-Mixing Support:** Moderate for native script dialogue (trained on `IN22-Conv`), but **zero native support for Latin-script WhatsApp code-mixing**.
- **License & Legal:** **MIT License.** Permissive, allows commercial use, redistribution, and fine-tuning.
- **Gating Requirements:** **Gated on HF.** Users must click "Agree and access repository" on the model card before accessing via token.
- **Card Contradictions / Missing Metadata:** The card recommends a newer model (`bodhan-ai/indic-translate`), which should also be monitored.

---

### Model 2: `ai4bharat/IndicXlit`
- **Repository Link:** [https://hf.co/ai4bharat/IndicXlit](https://hf.co/ai4bharat/IndicXlit)
- **Model Type:** Phonetic Transliteration Engine (Sequence-to-Sequence)
- **Base Architecture:** Fairseq Transformer (`indicxlit-en-indic-v1.0` and `indicxlit-indic-en-v1.0`)
- **Model Size / Files:** `indicxlit.pt` is **138.1 MB** (Fairseq checkpoint). Highly compact.
- **Format & Ollama Compatibility:** **Incompatible with Ollama.** Operates as an independent Fairseq / PyTorch transliteration module via the `ai4bharat-transliteration` Python package or standalone ONNX runtimes.
- **Script & Romanization Support:** **Explicitly Romanized input to native script output.** Specifically converts Latin-script phonetic Indic text into native Kannada script (`kn`).
- **Colloquial & Code-Mixing Support:** Handles phonetic variations well (*ivattu*, *yenu*, *madtira*), though it operates strictly at the word/character transliteration level without semantic translation to English.
- **License & Legal:** **MIT License.** Free for commercial use, redistribution, and modification.
- **Gating Requirements:** None. Open access.
- **Card Contradictions / Missing Metadata:** The main README contains only 24 bytes pointing to the research paper. Detailed usage documentation must be referenced from the GitHub repository (`AI4Bharat/IndicXlit`).

---

### Model 3: `RakshithFury/qwen3-4b-codemixed-kan-en`
- **Repository Link:** [https://hf.co/RakshithFury/qwen3-4b-codemixed-kan-en](https://hf.co/RakshithFury/qwen3-4b-codemixed-kan-en)
- **Model Type:** Causal Language Model / Structured JSON Normalizer & Translator
- **Base Architecture:** `Qwen3-4B` / `unsloth/Qwen3-4B-unsloth-bnb-4bit` (4,022.5M parameters)
- **Model Size / Files:** Full merged safetensors: `model-00001-of-00002.safetensors` (5.0 GB) + `model-00002-of-00002.safetensors` (3.1 GB) = **~8.1 GB**.
- **Format & Ollama Compatibility:** **Highly compatible with conversion.** Because it is an autoregressive Qwen causal LM with full merged safetensors and standard tokenizer files (`tokenizer.json`, `config.json`), it can be converted to GGUF format via `llama.cpp` (`convert_hf_to_gguf.py`) and imported directly into Ollama with a custom Modelfile.
- **Script & Romanization Support:** **Full native support for Romanized Kannada.** Specifically trained on informal Latin-script Kannada, mixed Kannada-English, and native Kannada script.
- **Colloquial & Code-Mixing Support:** **Verified and purpose-built.** The model was explicitly fine-tuned on 22,000 examples (including manual gold WhatsApp messages) to take inputs like `"ivattu office ge baralla swalpa fever ide"` and output structured JSON containing the faithful `english_translation`, `kannada_script`, and token-level language tags.
- **License & Legal:** ⚠️ **`CC-BY-NC-4.0` (Non-Commercial Only).** The author explicitly notes that the non-commercial restriction is inherited because synthetic training data was derived from `ai4bharat/samanantar`. Commercial use and commercial redistribution are **prohibited**.
- **Gating Requirements:** None. Open access.
- **Card Contradictions / Missing Metadata:** The README title calls itself a "LoRA", but the repository actually contains the **fully merged, unquantized 8.1 GB safetensors weights**, making it much easier to quantize to GGUF than a standalone adapter.

---

### Model 4: `Noxus09/code-mixed-translation`
- **Repository Link:** [https://hf.co/Noxus09/code-mixed-translation](https://hf.co/Noxus09/code-mixed-translation)
- **Model Type:** Causal LM Decoder for Code-Mixed Translation
- **Base Architecture:** LLaMA / Unsloth fine-tune
- **Model Size / Files:** `unsloth.Q4_K_M.gguf` (**4.4 GB**).
- **Format & Ollama Compatibility:** **Directly compatible with Ollama.** Provided as an out-of-the-box GGUF file (`Q4_K_M`). Can be loaded into Ollama immediately via `ollama create -f Modelfile`.
- **Script & Romanization Support:** Supports Romanized text, but **primarily Hindi/Hinglish**.
- **Colloquial & Code-Mixing Support:** **Unsupported for Kannada.** Documented examples in the card only demonstrate Hinglish ("Sun ka diameter kya hoga?"). Inspection of repository files reveals no evidence of Kannada or Kanglish training data.
- **License & Legal:** **Apache-2.0** in metadata; text mentions MIT. Permissive and commercial-friendly.
- **Gating Requirements:** None. Open access.
- **Card Contradictions / Missing Metadata:** No dataset provenance is specified ("smaller dataset of translated sentences"). Kannada support is neither claimed nor demonstrated.

---

### Model 5: `mahimaaruna04/qwen-kannada-translation`
- **Repository Link:** [https://hf.co/mahimaaruna04/qwen-kannada-translation](https://hf.co/mahimaaruna04/qwen-kannada-translation)
- **Model Type:** PEFT LoRA Adapter for Translation
- **Base Architecture:** Causal LM LoRA (`target_modules`: q, k, v, o, gate, up, down proj)
- **Model Size / Files:** `adapter_model.safetensors` (**73.9 MB**).
- **Format & Ollama Compatibility:** Requires merging the adapter into base Qwen weights (`Qwen/Qwen2.5-1.5B-Instruct`) and quantizing to GGUF before running in Ollama.
- **Script & Romanization Support:** **Native Kannada script only.** Trained strictly on native Kannada (`ಕನ್ನಡ`) ↔ English. Does not support Romanized Kanglish.
- **Colloquial & Code-Mixing Support:** Low. Trained on ~2,000 synthetic general translation pairs generated by Gemini/GPT prompting.
- **License & Legal:** **Apache-2.0.** Permissive.
- **Gating Requirements:** None. Open access.
- **Card Contradictions / Missing Metadata:** **Major technical contradiction.** The README claims the base model is `Qwen-1.8B` and calls it an "Encoder-decoder translation fine-tune" with a broken code example using `AutoModelForSeq2SeqLM`. However, `adapter_config.json` reveals the true base model is `Qwen/Qwen2.5-1.5B-Instruct` with `task_type: CAUSAL_LM`.

---

## 3. Datasets Audit

### Dataset 1: `ramachandrajoshi/english-kannada-cleaned`
- **Repository Link:** [https://hf.co/datasets/ramachandrajoshi/english-kannada-cleaned](https://hf.co/datasets/ramachandrajoshi/english-kannada-cleaned)
- **Task & Domain:** General Machine Translation (Bitext parallel sentences)
- **Volume & Splits:** **802,000 verified pairs** (Train: 800k, Validation: 1k, Test: 1k). Parquet size: 88.5 MB.
- **Language & Script Coverage:** English (`eng_Latn`) ↔ Native Kannada script (`kan_Knda`).
- **Kanglish & Code-Mixing Evidence:** **None.** Sentences are formal, curated standard translations (e.g. *"ಈ ಹಾಡನ್ನು ಸಲ್ಮಾನ್ ಖಾನ್ ಹಾಡಿದ್ದಾರೆ"*).
- **License & Legal:** **Apache-2.0.** Fully open for commercial training, modification, and redistribution.
- **Gating Requirements:** None. Open access.
- **Card Contradictions / Missing Metadata:** Text summary says "Total: 5,02,000 sentence pairs" while the split table and verified parquet files contain 802,000 rows.

---

### Dataset 2: `ai4bharat/Aksharantar`
- **Repository Link:** [https://hf.co/datasets/ai4bharat/Aksharantar](https://hf.co/datasets/ai4bharat/Aksharantar)
- **Task & Domain:** Word-level Transliteration & Romanization Lexicon
- **Volume & Splits:** **26 Million pairs across 20 languages.** Dedicated Kannada (`kan.zip`, 87.6 MB) contains:
  - **Training:** 2,907,000 word pairs
  - **Validation:** 7,000 word pairs
  - **Test:** 6,396 word pairs
- **Language & Script Coverage:** Explicitly maps Romanized Latin letters (`english word`) to native Kannada script (`native word`).
- **Kanglish & Code-Mixing Evidence:** **High vocabulary overlap.** While not sentence-level, it contains millions of phonetic spellings matching informal Kanglish (*swabhimanik*, *ivattu*, *nange*, *madbeku*).
- **License & Legal:** **CC0 (Public Domain) and CC-BY 4.0.** Mined data from Samanantar/IndicCorp is released under **CC0**; manually verified benchmark splits are under **CC-BY 4.0**. Exceptionally safe for commercial and open-source use.
- **Gating Requirements:** None. Direct download of `kan.zip`.
- **Card Contradictions / Missing Metadata:** HF Dataset Viewer throws a 500 casting error due to raw zip packaging; data must be inspected via direct archive download.

---

### Dataset 3: `ai4bharat/IN22-Conv` (and `mteb/IN22-Conv`)
- **Repository Link:** [https://hf.co/datasets/ai4bharat/IN22-Conv](https://hf.co/datasets/ai4bharat/IN22-Conv) | Mirror: [https://hf.co/datasets/mteb/IN22-Conv](https://hf.co/datasets/mteb/IN22-Conv)
- **Task & Domain:** Conversational Machine Translation Benchmark
- **Volume & Splits:** **1,503 multi-turn conversational sentence pairs** spanning 22 Indic languages and English.
- **Language & Script Coverage:** Spoken Kannada in native script (`kan_Knda`) ↔ English (`eng_Latn`).
- **Kanglish & Code-Mixing Evidence:** **High colloquial dialogue match.** Features natural spoken syntax, conversational contractions, and chat vocabulary (e.g. *"ಅಮ್ಮಾ, ನಾಳೆ ನಾವು ಸಿನ್ಮಾ ನೋಡಕ್‌ ಹೋಗಣ"*, *"ನಂಗೆ ಸ್ಕೂಲಿಲ್ಲ"*). However, it is written in **native Kannada script**, not Latin letters.
- **License & Legal:** **CC-BY-4.0.** Fully open for commercial reuse and fine-tuning with attribution.
- **Gating Requirements:** The upstream `ai4bharat/IN22-Conv` repo is gated. The identical benchmark is mirrored openly without gating at `mteb/IN22-Conv`.
- **Card Contradictions / Missing Metadata:** None. Clean schema verified via parquet inspection.

---

### Dataset 4: `ai4bharat/samanantar`
- **Repository Link:** [https://hf.co/datasets/ai4bharat/samanantar](https://hf.co/datasets/ai4bharat/samanantar)
- **Task & Domain:** Large-Scale Parallel Corpus
- **Volume & Splits:** 49.8M pairs across 11 languages. Kannada split (`kn`) contains **4,100,000 sentence pairs** (483.5 MB parquet).
- **Language & Script Coverage:** English (`en`) ↔ Native Kannada script (`kn`).
- **Kanglish & Code-Mixing Evidence:** **None.** Text is crawled from government websites, news archives, and Wikipedia. Minimal casual or chat-slang coverage.
- **License & Legal:** ⚠️ **`CC-BY-NC-4.0` (Strictly Non-Commercial).** Any model or derived dataset trained directly on Samanantar inherits this non-commercial restriction.
- **Gating Requirements:** None. Open access.
- **Card Contradictions / Missing Metadata:** None.

---

### Additional Discovered Dataset: `Anvesh-Lankala/Copy_Dakshina_Google_research_dataset`
- **Repository Link:** [https://hf.co/datasets/Anvesh-Lankala/Copy_Dakshina_Google_research_dataset](https://hf.co/datasets/Anvesh-Lankala/Copy_Dakshina_Google_research_dataset)
- **Task & Domain:** Sentence-level & Word-level Transliteration Benchmark (Google Research Dakshina)
- **Volume & Splits:** **10,000 full sentences for Kannada (`kn`)**, including multi-reference romanizations and token-level alignments.
- **Language & Script Coverage:** Native Kannada script (`native`) ↔ Romanized Latin-script Kannada (`romanized`).
- **Kanglish & Code-Mixing Evidence:** **Very High.** Provides real human variations of Romanized spellings for identical Kannada words (e.g. `["kurithu", "kuritu"]`, `["maadiddu", "madiddu"]`).
- **License & Legal:** **CC-BY-SA-4.0.** Open source, allows commercial use with ShareAlike requirements.
- **Gating Requirements:** None. Parquet exports fully readable.
- **Card Contradictions / Missing Metadata:** None. Verified via schema preview.

---

## 4. Comprehensive Comparison Tables

### Models Comparison Matrix

| Model Identifier | Architecture | Size | Native Script | Romanized Kanglish | Code-Mixed WhatsApp | Ollama Compatible | Declared License | Gated? |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`RakshithFury/qwen3-4b-codemixed-kan-en`** | Qwen Causal LM | 4.0B (~8.1 GB) | Yes | **Yes (Native)** | **Yes (Verified)** | **Yes (via GGUF)** | ⚠️ `CC-BY-NC-4.0` | No |
| **`ai4bharat/indictrans2-indic-en-dist-200M`** | IndicTrans Seq2Seq | 228M (~913 MB) | **Yes** | No (`kan_Knda` only) | No | No (Custom PyTorch) | **MIT** | **Yes** |
| **`ai4bharat/IndicXlit`** | Fairseq Seq2Seq | ~138 MB | Output only | **Input only** | Words only | No (Fairseq/ONNX) | **MIT** | No |
| **`Noxus09/code-mixed-translation`** | LLaMA Causal LM | 4.4 GB (GGUF) | No | Yes (Hindi only) | Hinglish only | **Yes (GGUF)** | Apache-2.0 | No |
| **`mahimaaruna04/qwen-kannada-translation`** | Qwen2.5-1.5B LoRA | 73.9 MB (LoRA) | **Yes** | No | No | Needs merge & GGUF | Apache-2.0 | No |

---

### Datasets Comparison Matrix

| Dataset Identifier | Domain | Size / Row Count | Native Script | Romanized Latin Script | Colloquial / Chat Slang | Commercial Safe? | License |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`ai4bharat/Aksharantar`** | Word Transliteration | 2.9M pairs (`kn`) | Yes | **Yes** | High (Phonetics) | **YES** | **CC0 / CC-BY-4.0** |
| **`ramachandrajoshi/english-kannada-cleaned`** | Clean Bitext MT | 802,000 pairs | Yes | No | Low (Formal) | **YES** | **Apache-2.0** |
| **`ai4bharat/IN22-Conv`** | Conversational Dialogue | 1,503 pairs | Yes | No | **High (Spoken syntax)** | **YES** | **CC-BY-4.0** |
| **`Anvesh-Lankala/Copy_Dakshina`** | Sentence Transliteration | 10,000 sentences | Yes | **Yes** | High (Spelling variants) | **YES** *(ShareAlike)* | **CC-BY-SA-4.0** |
| **`ai4bharat/samanantar`** | General Bitext MT | 4,100,000 pairs | Yes | No | Low (Web crawl) | ⚠️ **NO** | `CC-BY-NC-4.0` |

---

## 5. Strategic Conclusions & Recommendations

### 1. Best Candidates to Benchmark Locally First
1. **`RakshithFury/qwen3-4b-codemixed-kan-en` (Converted to GGUF):**
   - **Why:** This is the *only* pre-existing model on Hugging Face explicitly trained on Latin-script Kanglish and code-mixed Kannada WhatsApp idioms with structured JSON output.
   - **How to test:** Quantize the merged safetensors to `Q4_K_M` GGUF using `llama.cpp` and import it into Ollama. Run your existing `scripts/score.py` over `data/test.csv`.
2. **Existing Local Qwen2.5:3b + Dynamic Glossary:**
   - **Why:** In our prior benchmark, this baseline achieved **3/3 (100%)** on `data/test.csv` with zero training overhead, running completely offline and free of non-commercial license encumbrances.

### 2. Best Datasets to Build a Curated Kanglish Training Corpus
If you decide to train or fine-tune a model specifically for Kanglish:
1. **`ai4bharat/Aksharantar` (`kn.zip`, CC0/CC-BY):**
   Extract the top 50,000 most frequent phonetic mappings to build a deterministic lookup and normalization table.
2. **`ai4bharat/IN22-Conv` (CC-BY-4.0):**
   Take the 1,503 conversational sentences and generate phonetic Kanglish variants using `Aksharantar` rules to create the first gold-standard conversational Kanglish-English parallel corpus.
3. **`Anvesh-Lankala/Copy_Dakshina` (CC-BY-SA-4.0):**
   Utilize the 10,000 sentence alignments to train a phonetic spelling normalizer that maps noisy user text (*"barthira"*, *"bartira"*, *"barthiraa"*) into canonical forms.

### 3. Safest Resources for Commercial Open-Source Use
If `kanglish-foss` aims for commercial usability (e.g. Apache-2.0 or MIT):
- **SAFE:**
  - `ai4bharat/Aksharantar` (CC0 / CC-BY-4.0)
  - `ramachandrajoshi/english-kannada-cleaned` (Apache-2.0)
  - `ai4bharat/IN22-Conv` (CC-BY-4.0)
  - `ai4bharat/indictrans2-indic-en-dist-200M` (MIT)
  - `ai4bharat/IndicXlit` (MIT)
- **CONTAMINATED / NON-COMMERCIAL:**
  - ❌ `ai4bharat/samanantar` (`CC-BY-NC-4.0`)
  - ❌ `RakshithFury/qwen3-4b-codemixed-kan-en` (`CC-BY-NC-4.0` — derived from Samanantar)
  - ❌ `facebook/nllb-200-distilled-600M` (`CC-BY-NC-4.0`)

### 4. Recommended Architectural Approach
To preserve your existing stdlib scripts, offline architecture, and benchmark reproducibility:

```
[User Kanglish Input]
          │
          ▼
┌──────────────────────────────────────────────┐
│  Phase 1: Deterministic Token Normalizer    │
│  - Match against data/glossary.csv           │
│  - Expand spelling variants via Aksharantar │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 2: Dynamic Prompt Augmentation        │
│  - scripts/glossary_run.py (v1_baseline)     │
│  - Injects matched vocabulary definitions    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 3: Offline LLM Inference (Ollama)    │
│  - Candidate A: qwen2.5:3b (Clean, MIT/Apache)│
│  - Candidate B: RakshithFury Qwen3-4B GGUF   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Phase 4: Automated Scoring (score.py)       │
│  - Whole-word matching & commentary penalty  │
│  - Logged to results/log.csv                 │
└──────────────────────────────────────────────┘
```

This modular approach preserves complete transparency, maintains zero runtime pip dependencies, and prevents licensing contamination while leveraging the best discoveries on Hugging Face.
