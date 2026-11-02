# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Addestramento QLoRA di un modello piccolo sui dati verificati (da eseguire con l'ambiente .venv-train).

  .venv-train\\Scripts\\python training\\train_lora.py --base unsloth/gemma-3-4b-it --out training/runs/gemma3-4b

Il modello di partenza resta compresso a 4 bit e fermo; si addestrano solo piccole matrici aggiuntive
(LoRA) sui livelli lineari del modello linguistico, cosi' basta una scheda video da 8 GB.
Si impara solo dalle risposte dell'assistente: il codice sbagliato degli esempi di correzione
("train": false) resta nel contesto ma non entra nella perdita.
"""
import argparse
import json
import sys
from pathlib import Path

PROIEZIONI = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


def leggi(percorso):
    percorso = Path(percorso)
    if not percorso.exists():
        return []
    return [json.loads(r) for r in percorso.read_text(encoding="utf-8").splitlines() if r.strip()]


def id_token(tokenizer, messaggi, **opzioni):
    risultato = tokenizer.apply_chat_template(messaggi, tokenize=True, **opzioni)
    if hasattr(risultato, "keys"):          # alcune versioni restituiscono un BatchEncoding
        risultato = risultato["input_ids"]
    return list(risultato)


def codifica(tokenizer, esempio, lunghezza_max):
    """Token della conversazione ed etichette: -100 (ignorato) tranne le risposte da imparare.

    I confini di ogni risposta si trovano applicando il template a prefissi crescenti della
    conversazione; se il template non e' coerente sui prefissi, l'esempio viene scartato."""
    messaggi = [{"role": m["role"], "content": m["content"]} for m in esempio["messages"]]
    ids = id_token(tokenizer, messaggi)
    if len(ids) > lunghezza_max:
        return None, "troppo lungo"
    etichette = [-100] * len(ids)
    for i, m in enumerate(esempio["messages"]):
        if m["role"] != "assistant" or m.get("train") is False:
            continue
        inizio = id_token(tokenizer, messaggi[:i], add_generation_prompt=True)
        fine = id_token(tokenizer, messaggi[:i + 1])
        if ids[:len(inizio)] != inizio or ids[:len(fine)] != fine or len(fine) <= len(inizio):
            return None, "template incoerente"
        etichette[len(inizio):len(fine)] = ids[len(inizio):len(fine)]
    if all(e == -100 for e in etichette):
        return None, "niente da imparare"
    return {"input_ids": ids, "labels": etichette}, None


def prepara(tokenizer, esempi, lunghezza_max):
    codificati, scartati = [], {}
    for esempio in esempi:
        c, motivo = codifica(tokenizer, esempio, lunghezza_max)
        if c is None:
            scartati[motivo] = scartati.get(motivo, 0) + 1
        else:
            codificati.append(c)
    return codificati, scartati


def main(argv=None):
    p = argparse.ArgumentParser(description="QLoRA su dati Tessera verificati")
    p.add_argument("--base", required=True, help="modello di partenza (nome su Hugging Face o cartella locale)")
    p.add_argument("--train", default="training/data/train.jsonl")
    p.add_argument("--val", default="training/data/val.jsonl")
    p.add_argument("--out", required=True, help="cartella della corsa, es. training/runs/gemma3-4b")
    p.add_argument("--epochs", type=float, default=2)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--rank", type=int, default=16)
    p.add_argument("--alpha", type=int, default=32)
    p.add_argument("--max-len", type=int, default=3072)
    p.add_argument("--grad-accum", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--dry-run", action="store_true", help="solo tokenizzazione e statistiche, senza caricare il modello")
    args = p.parse_args(argv)

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    addestramento, scartati = prepara(tokenizer, leggi(args.train), args.max_len)
    validazione, _ = prepara(tokenizer, leggi(args.val), args.max_len)
    lunghezze = sorted(len(e["input_ids"]) for e in addestramento)
    print(f"esempi: {len(addestramento)} addestramento, {len(validazione)} validazione; scartati: {scartati}")
    if lunghezze:
        print(f"token per esempio: mediana {lunghezze[len(lunghezze) // 2]}, massimo {lunghezze[-1]}")
    if not addestramento:
        sys.exit("nessun esempio da addestrare: prima python -m training dataset")
    if args.dry_run:
        return 0

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, Trainer, TrainingArguments

    if not torch.cuda.is_available():
        sys.exit("serve una scheda video NVIDIA con CUDA")
    torch.manual_seed(args.seed)
    quantizzazione = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                        bnb_4bit_compute_dtype=torch.bfloat16)
    modello = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=quantizzazione, dtype=torch.bfloat16, device_map={"": 0},
        # Gemma 3 si addestra meglio con l'attenzione "eager" (raccomandazione di Google)
        attn_implementation="eager" if "gemma" in args.base.lower() else "sdpa")
    modello = prepare_model_for_kbit_training(modello, use_gradient_checkpointing=True)
    # Solo il modello linguistico: le parti per immagini o audio (se ci sono) restano ferme.
    bersagli = sorted({nome for nome, _ in modello.named_modules()
                       if nome.split(".")[-1] in PROIEZIONI and "vision" not in nome and "audio" not in nome})
    modello = get_peft_model(modello, LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=0.05,
                                                 target_modules=bersagli, task_type="CAUSAL_LM"))
    modello.print_trainable_parameters()

    def unisci(lotto):
        lunghezza = max(len(e["input_ids"]) for e in lotto)
        riempi = lambda seq, val: seq + [val] * (lunghezza - len(seq))      # noqa: E731
        return {
            "input_ids": torch.tensor([riempi(e["input_ids"], tokenizer.pad_token_id) for e in lotto]),
            "labels": torch.tensor([riempi(e["labels"], -100) for e in lotto]),
            "attention_mask": torch.tensor([riempi([1] * len(e["input_ids"]), 0) for e in lotto]),
        }

    uscita = Path(args.out)
    parametri = TrainingArguments(
        output_dir=str(uscita / "checkpoints"), per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum, num_train_epochs=args.epochs, learning_rate=args.lr,
        lr_scheduler_type="cosine", warmup_ratio=0.03, logging_steps=5, bf16=True, optim="paged_adamw_8bit",
        gradient_checkpointing=True, eval_strategy="epoch" if validazione else "no", save_strategy="epoch",
        save_total_limit=2, report_to=[], remove_unused_columns=False, seed=args.seed)
    trainer = Trainer(model=modello, args=parametri, train_dataset=addestramento,
                      eval_dataset=validazione or None, data_collator=unisci)
    trainer.train()

    modello.save_pretrained(uscita / "adapter")
    tokenizer.save_pretrained(uscita / "adapter")
    (uscita / "train_info.json").write_text(json.dumps({
        "base": args.base, "args": vars(args), "examples": len(addestramento), "val_examples": len(validazione),
        "skipped": scartati, "log": trainer.state.log_history}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAdattatore salvato in {uscita / 'adapter'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
