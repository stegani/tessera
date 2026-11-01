"""Sentinella hardware, versione minima: controlla la clausola platform di un process prima dell'avvio.

Regola: se un requisito non si puo' verificare su questa macchina, il process non parte.
"""
import platform
from pathlib import Path

from .errori import ErroreTessera

VULNERABILITA = Path("/sys/devices/system/cpu/vulnerabilities")


def _mitigazioni_spectre():
    """Su Linux il kernel dichiara lo stato di ogni vulnerabilita' della CPU."""
    if platform.system() != "Linux" or not VULNERABILITA.is_dir():
        return None
    for nome in ("spectre_v1", "spectre_v2"):
        f = VULNERABILITA / nome
        if not f.exists() or f.read_text().strip().startswith("Vulnerable"):
            return False
    return True


def _ecc():
    """Su Linux il sottosistema EDAC elenca i controller di memoria con correzione degli errori."""
    if platform.system() != "Linux":
        return None
    controller = Path("/sys/devices/system/edac/mc")
    return controller.is_dir() and any(controller.glob("mc*"))


RILEVATORI = {"spectre_mitigations": _mitigazioni_spectre, "ecc": _ecc}


def controlla_piattaforma(proc):
    for requisito in proc.piattaforma:
        rilevatore = RILEVATORI.get(requisito)
        esito = rilevatore() if rilevatore else None
        if esito is None:
            raise ErroreTessera("sicurezza", f"la sentinella non sa verificare '{requisito}' su questa macchina "
                                             f"({platform.system()}): process {proc.nome} non avviato", riga=proc.riga,
                                suggerimento="togli il requisito o esegui su una piattaforma che lo dichiara")
        if esito is False:
            raise ErroreTessera("sicurezza", f"requisito '{requisito}' non soddisfatto: process {proc.nome} non avviato",
                                riga=proc.riga)
