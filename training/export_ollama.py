# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Unisce l'adattatore LoRA al modello di partenza e registra il risultato in Ollama.

  .venv-train\\Scripts\\python training\\export_ollama.py --run training/runs/gemma3-4b ^
      --base unsloth/gemma-3-4b-it --ollama-base gemma3:4b --name tessera-gemma3:4b

Il template della conversazione, i parametri e la licenza si copiano dal modello Ollama di partenza,
cosi' il modello addestrato si usa esattamente come l'originale (per Gemma la licenza va conservata).
Poi:  python -m experiment run --model ollama:tessera-gemma3:4b
"""
import argparse
import subprocess
import sys
from pathlib import Path


def modelfile(ollama_base, cartella_pesi):
    """Il Modelfile del modello di partenza, con FROM sostituito dalla cartella dei pesi uniti."""
    originale = subprocess.run(["ollama", "show", ollama_base, "--modelfile"], capture_output=True, text=True,
                               encoding="utf-8", check=True).stdout
    righe = [r for r in originale.splitlines() if not r.startswith("FROM ") and not r.startswith("#")]
    return f"FROM {cartella_pesi}\n" + "\n".join(righe).strip() + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Esporta il modello addestrato in Ollama")
    p.add_argument("--run", required=True, help="cartella della corsa (contiene adapter/)")
    p.add_argument("--base", required=True, help="lo stesso modello di partenza usato per l'addestramento")
    p.add_argument("--ollama-base", required=True, help="il modello Ollama corrispondente, es. gemma3:4b")
    p.add_argument("--name", required=True, help="nome del nuovo modello in Ollama, es. tessera-gemma3:4b")
    p.add_argument("--quantize", default="q4_K_M", help="quantizzazione in Ollama (vuoto per nessuna)")
    args = p.parse_args(argv)

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    corsa = Path(args.run)
    uniti = corsa / "merged"
    print("Unione dell'adattatore (sul processore, in bf16)...")
    modello = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.bfloat16, device_map={"": "cpu"})
    modello = PeftModel.from_pretrained(modello, corsa / "adapter").merge_and_unload()
    modello.save_pretrained(uniti, safe_serialization=True)
    AutoTokenizer.from_pretrained(corsa / "adapter").save_pretrained(uniti)

    file_modello = corsa / "Modelfile"
    file_modello.write_text(modelfile(args.ollama_base, "./merged"), encoding="utf-8")
    comando = ["ollama", "create", args.name, "-f", str(file_modello)]
    if args.quantize:
        comando += ["--quantize", args.quantize]
    print(" ".join(comando))
    subprocess.run(comando, check=True)
    print(f"\nPronto: python -m experiment run --model ollama:{args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
