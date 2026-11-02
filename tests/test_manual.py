# Copyright 2026 Stefano Stegani - Airgrid Network - www.airgrid.it
# SPDX-License-Identifier: Apache-2.0
"""Ogni programma completo del manuale (blocchi ```tessera) deve compilare, superare i suoi esempi e girare."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
MANUALI = [RADICE / "docs" / "manual.md", RADICE / "docs" / "manual.it.md"]


def programmi():
    for manuale in MANUALI:
        if not manuale.exists():
            continue
        for i, codice in enumerate(re.findall(r"```tessera\n(.*?)```", manuale.read_text(encoding="utf-8"), re.DOTALL)):
            yield pytest.param(codice, id=f"{manuale.stem}-{i + 1}-{codice.split()[1]}")


def tessera(*argomenti):
    ambiente = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "tessera", *argomenti], cwd=RADICE, env=ambiente,
                          capture_output=True, text=True, encoding="utf-8")


def test_ci_sono_programmi():
    assert len(list(programmi())) >= 10


@pytest.mark.parametrize("codice", programmi())
def test_programma_del_manuale(codice, tmp_path):
    assert codice.startswith("module "), "un blocco tessera deve essere un programma completo"
    file = tmp_path / "programma.tsr"
    file.write_text(codice, encoding="utf-8")
    for comando in ("check", "test"):
        esito = tessera(comando, str(file))
        assert esito.returncode == 0, f"{comando}: {esito.stdout}{esito.stderr}"
    if re.search(r"^(process main|fn main\(\))", codice, re.MULTILINE):
        esito = tessera("run", str(file))
        assert esito.returncode == 0, f"run: {esito.stdout}{esito.stderr}"
