"""Ejecuta las órdenes pendientes de config/cola_estudios.txt (solo «tbot research studyNN») y las marca como hechas."""

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COLA = Path("config/cola_estudios.txt")
ORDEN = re.compile(r"^tbot research study\d{1,3}$")


def main() -> int:
    text = COLA.read_text(encoding="utf-8").splitlines()
    i_pend, i_done = text.index("[pendientes]"), text.index("[hechas]")
    pending = [ln.strip() for ln in text[i_pend + 1:i_done] if ln.strip() and not ln.startswith("#")]
    done_lines = text[i_done + 1:]
    fallos = 0
    for cmd in pending:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if not ORDEN.match(cmd):
            done_lines.append(f"{cmd}  # IGNORADA {stamp}: no tiene la forma «tbot research studyNN»")
            continue
        print(f"== {cmd}", flush=True)
        r = subprocess.run(cmd.split(), check=False)
        estado = "ok" if r.returncode == 0 else f"FALLÓ (código {r.returncode})"
        fallos += r.returncode != 0
        done_lines.append(f"{cmd}  # {estado} {stamp}")
    COLA.write_text("\n".join(text[:i_pend + 1] + ["[hechas]"] + done_lines) + "\n", encoding="utf-8")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
