"""
scripts/train_kanglish_1.5b_lora.py
Fine-tunes Qwen2.5-1.5B-Instruct on the Master Kanglish Dataset
(names, animals, slang, elongated letters, and daily conversational sentences)
using PEFT LoRA and gradient checkpointing on an RTX 3050 6GB GPU.
"""

import os
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq
)

def main():
    model_id = "Qwen/Qwen2.5-1.5B-Instruct"
    data_path = "data/processed/kanglish_master_train.jsonl"
    output_dir = "models/kanglish_qwen_1.5b_lora"
    merged_output_dir = "models/kanglish_qwen_1.5b_merged"

    print("=" * 65)
    print("Kanglish -> English 1.5B Model Training Pipeline")
    print(f"Base Model : {model_id}")
    print(f"Dataset    : {data_path}")
    print(f"Device     : {torch.cuda.get_device_name(0)} ({round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2)} GB)")
    print("=" * 65)

    # 1. Load Tokenizer
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 2. Load & Format Dataset
    print(f"Loading dataset from {data_path}...")
    raw_dataset = load_dataset("json", data_files=data_path)["train"]

    def format_chat(sample):
        text = tokenizer.apply_chat_template(sample["messages"], tokenize=False)
        encodings = tokenizer(
            text,
            max_length=256,
            truncation=True,
            padding=False
        )
        encodings["labels"] = encodings["input_ids"].copy()
        return encodings

    tokenized_dataset = raw_dataset.map(format_chat, remove_columns=raw_dataset.column_names)
    print(f"Dataset ready: {len(tokenized_dataset)} samples.")

    # 3. Load Base Model in FP16 with Gradient Checkpointing
    print("Loading 1.5B base model in FP16...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    # 4. Configure LoRA
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 5. Training Arguments (optimized for 6GB VRAM)
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        warmup_steps=15,
        num_train_epochs=3,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=15,
        save_strategy="no",
        report_to="none"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt")
    )

    # 6. Train
    print("\nStarting LoRA Fine-Tuning on 1.5B Model...")
    trainer.train()

    # 7. Merge and Save Weights
    print(f"\nMerging LoRA adapter with base model to {merged_output_dir}...")
    merged_model = model.merge_and_unload()
    os.makedirs(merged_output_dir, exist_ok=True)
    merged_model.save_pretrained(merged_output_dir)
    tokenizer.save_pretrained(merged_output_dir)

    print("\n" + "=" * 65)
    print("1.5B Model Training and weight merging complete!")
    print(f"Saved merged model at: {merged_output_dir}")
    print("=" * 65)

if __name__ == "__main__":
    main()
