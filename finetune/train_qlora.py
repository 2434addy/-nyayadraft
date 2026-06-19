"""QLoRA SFT for Qwen2.5-7B on the NyayaDraft dataset.

4-bit NF4 base + LoRA adapters, completion-only loss (the prompt is masked; the
model is trained only to produce the document), Qwen's own chat template applied
at train time. Hyperparameters are tuned for a SMALL (~750-example) corpus: few
epochs, eval + early-stopping on held-out val loss, weight decay + LoRA dropout
to guard against overfitting.

This script is GPU-only — do not run it on the prep machine. See finetune/README.md
for cloud-GPU instructions and the exact pinned environment (requirements.txt).

Validated against: torch 2.4.x, transformers 4.46.x, trl 0.12.x, peft 0.13.x,
bitsandbytes 0.44.x, accelerate 1.1.x, datasets 3.1.x.

Example:
  python finetune/train_qlora.py \
      --model Qwen/Qwen2.5-7B-Instruct \
      --data-dir finetune/data \
      --output-dir finetune/out/qwen2.5-7b-nyayadraft-qlora
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    EarlyStoppingCallback,
)
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

# Qwen2.5 ChatML assistant header. Completion-only masking trains the loss only
# on tokens AFTER this marker (the document + closing <|im_end|>), never on the
# system prompt or user request.
RESPONSE_TEMPLATE = "<|im_start|>assistant\n"

# All attention + MLP projections — full LoRA coverage for a 7B decoder.
LORA_TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="QLoRA SFT for Qwen2.5-7B (NyayaDraft).")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct",
                   help="HF model id. Use the -Instruct variant (chat template + "
                        "system-prompt support); pass the base Qwen2.5-7B only if "
                        "you want to teach the chat format from scratch.")
    p.add_argument("--data-dir", default="finetune/data")
    p.add_argument("--output-dir", default="finetune/out/qwen2.5-7b-nyayadraft-qlora")
    # LoRA
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    # Optimisation (tuned for ~750 examples)
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=16)  # effective batch = 16
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--max-seq-len", type=int, default=4096)  # max record ~3.6k tok
    p.add_argument("--weight-decay", type=float, default=0.01)
    p.add_argument("--warmup-ratio", type=float, default=0.03)
    p.add_argument("--early-stopping-patience", type=int, default=2)
    p.add_argument("--seed", type=int, default=20260610)
    # Toggles
    p.add_argument("--merge", action="store_true",
                   help="After training, merge the adapter into fp16 weights and "
                        "save a standalone model (needs extra disk + RAM).")
    p.add_argument("--flash-attn", action="store_true",
                   help="Use flash_attention_2 (requires the flash-attn wheel); "
                        "default is PyTorch SDPA, which needs no extra install.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    if tokenizer.pad_token is None:
        # Pad with EOS; the collator masks pad/label positions to -100 anyway.
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"  # required for SFT loss alignment

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2" if args.flash_attn else "sdpa",
    )
    model.config.use_cache = False  # incompatible with gradient checkpointing
    model.config.pretraining_tp = 1

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=LORA_TARGET_MODULES,
    )

    dataset = load_dataset(
        "json",
        data_files={
            "train": str(data_dir / "train.jsonl"),
            "validation": str(data_dir / "val.jsonl"),
        },
    )

    def formatting_func(batch: dict) -> list[str]:
        # Render each conversation with Qwen's OWN chat template (ChatML). This is
        # the canonical "formatted with Qwen's chat template" step; we never
        # hardcode the template string.
        return [
            tokenizer.apply_chat_template(msgs, tokenize=False)
            for msgs in batch["messages"]
        ]

    # Completion-only collator: mask everything up to and including the assistant
    # header so loss is computed solely on the generated document. Passing token
    # ids (not the raw string) avoids the ChatML retokenisation mismatch.
    response_ids = tokenizer.encode(RESPONSE_TEMPLATE, add_special_tokens=False)
    collator = DataCollatorForCompletionOnlyLM(
        response_template=response_ids,
        tokenizer=tokenizer,
    )

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=args.warmup_ratio,
        weight_decay=args.weight_decay,
        max_grad_norm=0.3,
        optim="paged_adamw_8bit",
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_seq_length=args.max_seq_len,
        packing=False,  # required for completion-only masking
        dataset_kwargs={"add_special_tokens": False},  # template already complete
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=args.seed,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
        peft_config=lora_config,
        formatting_func=formatting_func,
        data_collator=collator,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=args.early_stopping_patience)],
    )

    trainer.train()

    # Persist the (best) adapter + tokenizer.
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"\nAdapter saved to {args.output_dir}")

    if args.merge:
        from peft import AutoPeftModelForCausalLM
        merged_dir = Path(args.output_dir) / "merged-fp16"
        merged = AutoPeftModelForCausalLM.from_pretrained(
            args.output_dir, torch_dtype=torch.float16, device_map="cpu",
        ).merge_and_unload()
        merged.save_pretrained(merged_dir, safe_serialization=True)
        tokenizer.save_pretrained(merged_dir)
        print(f"Merged fp16 model saved to {merged_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
