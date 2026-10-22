"""
Kanglish 0.5B v2 fine-tune.
Compatible with: transformers 5.x, trl 1.16, Windows (spawn-safe).

Key design:
  - if __name__ == '__main__' guard (Windows multiprocessing)
  - TOKENIZERS_PARALLELISM=false
  - Pre-format all chat templates in plain Python loop (no dataset.map subprocess)
  - dataloader_num_workers=0 (no worker processes on Windows)
  - warmup_steps instead of warmup_ratio (transformers 5.x)
  - trl 1.16 SFTTrainer: uses processing_class + formatting_func, not tokenizer/dataset_text_field
"""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig, get_peft_model, PeftModel
from trl import SFTTrainer, SFTConfig

BASE_MODEL = "models/kanglish_qwen_0.5b_merged"
TRAIN_FILE = "data/processed/kanglish_clean_train.jsonl"
OUTPUT_DIR = "models/kanglish_qwen_0.5b_v2_lora"
MERGED_DIR = "models/kanglish_qwen_0.5b_v2_merged"


def main():
    print("=" * 60)
    print("KANGLISH 0.5B RE-FINE-TUNE v2")
    print("transformers 5.x + trl 1.16 + Windows-safe")
    print("=" * 60)

    # ── Load raw records ──────────────────────────────────────
    records = []
    with open(TRAIN_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Training records loaded: {len(records)}")

    # ── Tokenizer ─────────────────────────────────────────────
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ── Pre-format ALL text in plain Python (no spawn needed) ─
    print("Formatting chat templates (single-process)...")
    formatted_texts = []
    for r in records:
        text = tokenizer.apply_chat_template(
            r["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        formatted_texts.append(text)
    print(f"Formatted {len(formatted_texts)} examples.")

    ds = Dataset.from_dict({"text": formatted_texts})
    ds = ds.train_test_split(test_size=0.02, seed=42)
    print(f"Train: {len(ds['train'])}  Val: {len(ds['test'])}")

    # ── Load model ────────────────────────────────────────────
    print("Loading base model...")
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    print(f"Running on: {'CUDA (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'CPU'}")

    # ── LoRA ──────────────────────────────────────────────────
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── SFTConfig (trl 1.16 uses SFTConfig instead of TrainingArguments) ──
    warmup_steps = max(1, int(0.05 * (len(ds['train']) // (4 * 4) * 4)))
    sft_config = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=4,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps,
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

    # ── Trainer ───────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=ds["train"],
        eval_dataset=ds["test"],
        processing_class=tokenizer,
    )

    print("\nStarting training...")
    trainer.train()

    print("\nSaving LoRA adapter...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # ── Merge LoRA into base ──────────────────────────────────
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
    print(f"\n[DONE] Merged model saved to: {MERGED_DIR}")
    print("Next: quantize to GGUF with llama.cpp")


if __name__ == "__main__":
    main()
