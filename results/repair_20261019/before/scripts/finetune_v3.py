"""
Kanglish 0.5B v3 Fine-Tuning Pipeline
Trained on Teacher-Distilled Gemini Dataset.

Features:
  - 100% Windows spawn-safe
  - Pre-tokenized chat templates
  - LoRA fine-tuning on Qwen2.5-0.5B
  - Automatic weight merge to float32
  - Automatic GGUF (Q8_0) quantization via llama.cpp
"""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
import subprocess
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, PeftModel
from trl import SFTTrainer, SFTConfig

BASE_MODEL = "models/kanglish_qwen_0.5b_merged"
TRAIN_FILE = "data/processed/kanglish_v3_train.jsonl"
OUTPUT_DIR = "models/kanglish_qwen_0.5b_v3_lora"
MERGED_DIR = "models/kanglish_qwen_0.5b_v3_merged"
GGUF_OUT = "mobile/android/app/build/outputs/apk/debug/kanglish_qwen_0.5b_v3.gguf"


def main():
    print("=" * 60)
    print("KANGLISH 0.5B v3 TRAINING (TEACHER-DISTILLED)")
    print("=" * 60)

    # 1. Load training records
    records = []
    with open(TRAIN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Total training records: {len(records)}")

    # 2. Tokenizer
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # 3. Format chat templates
    print("Formatting chat templates...")
    formatted_texts = []
    for r in records:
        text = tokenizer.apply_chat_template(
            r["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        formatted_texts.append(text)

    # Split 98% train, 2% val
    split_idx = int(len(formatted_texts) * 0.98)
    train_texts = formatted_texts[:split_idx]
    val_texts = formatted_texts[split_idx:]
    print(f"Train samples: {len(train_texts)} | Val samples: {len(val_texts)}")

    ds = {
        "train": Dataset.from_dict({"text": train_texts}),
        "test": Dataset.from_dict({"text": val_texts}),
    }

    # 4. Load base model
    print("Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
        trust_remote_code=True,
    )

    # 5. LoRA Configuration
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 6. SFTConfig
    sft_config = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=4,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=50,
        weight_decay=0.01,
        fp16=torch.cuda.is_available(),
        logging_steps=25,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=2,
        load_best_model_at_end=True,
        report_to="none",
        dataloader_num_workers=0,
        max_length=256,
        dataset_text_field="text",
        seed=42,
    )

    # 7. Trainer
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=ds["train"],
        eval_dataset=ds["test"],
        processing_class=tokenizer,
    )

    print("\nStarting training on GPU...")
    trainer.train()

    print("\nSaving LoRA adapter...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # 8. Merge LoRA into base model
    print("\nMerging LoRA weights into base model...")
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )
    merged = PeftModel.from_pretrained(base, OUTPUT_DIR)
    merged = merged.merge_and_unload()
    merged.save_pretrained(MERGED_DIR)
    tokenizer.save_pretrained(MERGED_DIR)
    print(f"\n[DONE] Merged v3 model saved to: {MERGED_DIR}")

    # 9. Quantize to GGUF
    print("\nQuantizing v3 model to Q8_0 GGUF...")
    convert_script = "mobile/android/third_party/llama.cpp/convert_hf_to_gguf.py"
    subprocess.run([
        "python", convert_script,
        MERGED_DIR,
        "--outtype", "q8_0",
        "--outfile", GGUF_OUT
    ], check=True)

    print(f"\n============================================================")
    print(f"[SUCCESS] v3 Model Ready: {GGUF_OUT}")
    print(f"============================================================")


if __name__ == "__main__":
    main()
