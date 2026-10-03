"""JSON estricto: el navegador rechaza NaN e Infinity, que Python escribe por defecto."""

from __future__ import annotations

import json
import math
from pathlib import Path


def finite(obj):
    """Copia de `obj` con los NaN/±Infinity convertidos en None (null en JSON)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [finite(v) for v in obj]
    return obj


def dumps(obj, **kw) -> str:
    """`json.dumps` que nunca emite NaN/Infinity."""
    return json.dumps(finite(obj), allow_nan=False, ensure_ascii=False, **kw)


def load(path: Path):
    """Lee un JSON aceptando NaN/Infinity (archivos ya generados) y los convierte en None."""
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=lambda _c: None)


def iter_jsonl(path: Path):
    """Recorre un .jsonl línea a línea: cada elemento es el dict leído o None si la línea está dañada.

    Tolera un corte a mitad de un carácter UTF-8 (apagón): la línea se descarta, no detiene la lectura.
    """
    p = Path(path)
    if not p.exists():
        return
    with open(p, "rb") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                yield None


def append_line(path: Path, line: str) -> None:
    """Agrega una línea a un .jsonl; si un apagón dejó la última cortada, empieza en una línea nueva."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    needs_nl = False
    if p.exists() and p.stat().st_size > 0:
        with open(p, "rb") as fh:
            fh.seek(-1, 2)
            needs_nl = fh.read(1) != b"\n"
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(("\n" if needs_nl else "") + line + "\n")
