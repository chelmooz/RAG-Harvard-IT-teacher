"""
Prof IA v6.0 — Fine-tuning QLoRA sur AMD BC-250 (ROCm 7.2)
============================================================
DIFFÉRENCES VS v4 (qui ciblait CUDA) :
  1. BitsAndBytesConfig désactivé → quantification manuelle AWQ/GPTQ
     (bitsandbytes CUDA ne fonctionne pas nativement sur ROCm BC-250)
  2. fp16=True (non bf16) : Cyan Skillfish RDNA2 = fp16 natif
  3. SFTTrainer (TRL) remplace Trainer : plus simple pour instruction tuning
  4. gradient_checkpointing=True : réduit la pression sur les 12 Go VRAM
  5. Sauvegarde directe asyncpg : récupère le golden dataset depuis PostgreSQL
"""

import asyncio
import os

# ── Variables ROCm — DOIT être défini AVANT tout import torch/transformers ──────
# Cyan Skillfish (gfx1013) est absent de la liste officielle ROCm.
# Sans cette variable, PyTorch ROCm refuse de reconnaître le BC-250 et
# retombe en mode CPU silencieusement.
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "max_split_size_mb:512")

import asyncpg
import torch
import yaml
from datasets import Dataset
from loguru import logger
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


async def fetch_golden_dataset(db_url: str, limit: int = 500) -> list[dict]:
    """
    Récupère le Golden Dataset directement depuis PostgreSQL 18.2.
    Plus rapide que passer par l'API REST pour le fine-tuning local.
    """
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.user_query   AS instruction,
                c.rag_context  AS input,
                c.model_response AS output,
                c.metier,
                e.auto_score
            FROM conversations c
            JOIN response_evaluations e ON c.id = e.conversation_id
            WHERE e.is_golden = true
            ORDER BY e.auto_score DESC, e.human_rating DESC NULLS LAST
            LIMIT $1;
            """,
            limit,
        )
    await pool.close()
    logger.info(f"⭐ {len(rows)} conversations Golden récupérées")
    return [dict(r) for r in rows]


def format_for_sft(records: list[dict]) -> list[dict]:
    """
    Convertit les enregistrements en format Alpaca pour SFTTrainer.
    Format : ### Instruction:\n...\n### Entrée:\n...\n### Réponse:\n...
    """
    formatted = []
    for r in records:
        ctx = r.get("input") or ""
        text = (
            f"### Instruction:\n{r['instruction']}\n\n"
            f"### Entrée (contexte RAG):\n{ctx}\n\n"
            f"### Réponse:\n{r['output']}"
        )
        formatted.append({"text": text})
    return formatted


def _load_model_with_lora(base_model: str, config: dict):
    logger.info(f"📦 Chargement modèle fp16 : {base_model}")
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False

    lora_cfg = config["lora"]
    lora_config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("alpha", 32),
        target_modules=lora_cfg.get("target_modules", ["q_proj", "v_proj"]),
        lora_dropout=lora_cfg.get("dropout", 0.05),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


def _create_training_args(output_dir: str, config: dict) -> TrainingArguments:
    train_cfg = config["training"]
    return TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=train_cfg.get("num_epochs", 3),
        per_device_train_batch_size=train_cfg.get("batch_size", 1),
        gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 8),
        learning_rate=train_cfg.get("learning_rate", 2e-4),
        fp16=True,
        bf16=False,
        gradient_checkpointing=True,
        save_steps=train_cfg.get("save_steps", 50),
        logging_steps=train_cfg.get("logging_steps", 10),
        warmup_steps=train_cfg.get("warmup_steps", 20),
        optim="adamw_torch",
        report_to="none",
        dataloader_num_workers=0,
    )


def main():
    logger.info("🚀 Prof IA v6.0 — Fine-tuning QLoRA (AMD BC-250 / ROCm 7.2)")

    config = load_config()
    db_url = config.get("database", {}).get(
        "url",
        "postgresql://REDACTED_USER@localhost:5432/prof_ia_v5"
    )
    base_model = config["model"]["base_model"]
    output_dir = config["training"]["output_dir"]

    # ── Récupérer le Golden Dataset ────────────────────────────────────────────
    records = asyncio.run(fetch_golden_dataset(db_url, limit=config["dataset"].get("limit", 500)))
    if not records:
        logger.error("❌ Aucune donnée Golden — lancez d'abord l'application pour générer des conversations.")
        return

    formatted = format_for_sft(records)
    dataset = Dataset.from_list(formatted)
    logger.info(f"📚 Dataset SFT : {len(dataset)} exemples")

    # ── Tokenizer ──────────────────────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = _load_model_with_lora(base_model, config)
    training_args = _create_training_args(output_dir, config)

    # ── SFTTrainer ─────────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=2048,    # Calibré pour 12 Go VRAM BC-250
        packing=False,
    )

    logger.info("🎯 Démarrage du fine-tuning...")
    trainer.train()

    logger.info(f"💾 Sauvegarde du modèle LoRA → {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    logger.info("✅ Fine-tuning terminé!")
    logger.info(f"   → Modèle LoRA sauvegardé dans : {output_dir}")
    logger.info("   → Pour convertir en GGUF : llama.cpp convert-hf-to-gguf.py")


if __name__ == "__main__":
    main()
