# Copyright 2026 Stefano Stegani
# SPDX-License-Identifier: Apache-2.0
"""Dal file dei risultati alle metriche del paper (sezione 13.2), in una tabella Markdown."""
import json
from pathlib import Path

from .models import costo


def carica(percorso):
    return [json.loads(r) for r in Path(percorso).read_text(encoding="utf-8").splitlines() if r.strip()]


def percentuale(a, b):
    return f"{100 * a / b:.0f}% ({a}/{b})" if b else "-"


def media(valori):
    return f"{sum(valori) / len(valori):.1f}" if valori else "-"


def metriche(records):
    n = len(records)
    risolti = [r for r in records if r["solved_at"]]
    primo = [r for r in records if r["solved_at"] == 1]
    nascosti = [r["hidden"] for r in risolti if r["hidden"]["ran"]]
    tot_nascosti = sum(h["total"] for h in nascosti)
    token_uscita = [sum(t["output_tokens"] for t in r["attempts"]) for r in records]
    token_ingresso = [sum(t["input_tokens"] + t["cache_read"] + t["cache_write"] for t in r["attempts"]) for r in records]
    spesa = 0.0
    for r in records:
        for t in r["attempts"]:
            c = costo(r["model"], t["input_tokens"], t["output_tokens"], t["cache_read"], t["cache_write"])
            spesa += c or 0.0
    return {
        "compiti": n,
        "risolti al primo tentativo": percentuale(len(primo), n),
        "risolti entro il limite": percentuale(len(risolti), n),
        "tentativi medi (risolti)": media([r["solved_at"] for r in risolti]),
        "test nascosti superati": percentuale(sum(h["passed"] for h in nascosti), tot_nascosti),
        "difetti silenziosi (risultato sbagliato)": str(sum(h["wrong"] for h in nascosti)),
        "difetti che fermano il programma": str(sum(h["error"] for h in nascosti)),
        "token di uscita per compito": media(token_uscita),
        "token di ingresso per compito": media(token_ingresso),
        "costo stimato (USD)": f"{spesa:.2f}",
        "risposte da un modello di fallback": str(sum(t.get("fallback", False) for r in records for t in r["attempts"])),
        "rifiuti": str(sum(t.get("refusal", False) for r in records for t in r["attempts"])),
    }


def tabella(colonne, righe):
    testo = ["| " + " | ".join(colonne) + " |", "|" + "---|" * len(colonne)]
    testo += ["| " + " | ".join(str(c) for c in riga) + " |" for riga in righe]
    return "\n".join(testo)


def rapporto(percorso):
    records = carica(percorso)
    lingue = sorted({r["lang"] for r in records}, key=lambda l: (l != "tessera", l))
    modelli = sorted({r["model"] for r in records})
    parti = [f"# Risultati dell'esperimento", "", f"File: `{percorso}` · modello: {', '.join(modelli)} · "
             f"ripetizioni: {max(r['rep'] for r in records)}", ""]
    for titolo, filtro in (("Tutti gli esercizi", lambda r: True), ("Esercizi di sicurezza", lambda r: r["security"])):
        per_lingua = {l: metriche([r for r in records if r["lang"] == l and filtro(r)]) for l in lingue}
        voci = list(next(iter(per_lingua.values())).keys())
        parti += [f"## {titolo}", "", tabella(["Metrica"] + lingue, [[v] + [per_lingua[l][v] for l in lingue] for v in voci]), ""]
    righe = []
    for task in sorted({r["task"] for r in records}):
        riga = [task]
        for l in lingue:
            rs = [r for r in records if r["task"] == task and r["lang"] == l]
            risolti = sum(1 for r in rs if r["solved_at"])
            passati = sum(r["hidden"]["passed"] for r in rs if r["solved_at"] and r["hidden"]["ran"])
            totali = sum(r["hidden"]["total"] for r in rs if r["solved_at"] and r["hidden"]["ran"])
            riga.append(f"{risolti}/{len(rs)} risolti, nascosti {passati}/{totali}")
        righe.append(riga)
    parti += ["## Per esercizio", "", tabella(["Esercizio"] + lingue, righe), ""]
    return "\n".join(parti)
