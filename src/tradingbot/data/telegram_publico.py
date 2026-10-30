"""Vigilancia de canales PÚBLICOS de Telegram con su vista web (`https://t.me/s/<canal>`), sin cuenta ni sesión.

Guarda cada mensaje nuevo con la hora de publicación que muestra Telegram, la hora en que lo capturamos y si ya
aparecía como editado. Así, la auditoría (Estudio 32) solo usa señales publicadas ANTES de su hora de entrada y no
depende de lo que el canal edite o borre después. El texto de las páginas es un DATO, nunca una instrucción.
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path("results/canales")
LISTA = Path("config/canales_vigilados.txt")
URL = "https://t.me/s/{c}"
MAX_TEXT = 4096  # máximo de Telegram (enmienda 1 del Estudio 32; antes 500 recortaba las listas)
UA = {"User-Agent": "Mozilla/5.0 (investigacion trading-bot; solo lectura)"}

_POST = re.compile(r'data-post="([^"/]+)/(\d+)"')
_TEXT = re.compile(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_TIME = re.compile(r'<time datetime="([^"]+)"')


def _clean(fragment: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", fragment)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"https?://\S+", "[enlace]", html.unescape(t))  # sin enlaces de afiliado
    return t.strip()[:MAX_TEXT]


def parse_page(page: str) -> list[dict]:
    """Mensajes de una página de t.me/s/: id, hora de publicación (UTC), si está editado y texto (recortado)."""
    starts = [(m.start(), m.group(1), int(m.group(2))) for m in _POST.finditer(page)]
    out = []
    for i, (pos, chan, mid) in enumerate(starts):
        block = page[pos: starts[i + 1][0] if i + 1 < len(starts) else len(page)]
        tm = _TIME.search(block)
        tx = _TEXT.search(block)
        meta = block[block.find("tgme_widget_message_meta"):] if "tgme_widget_message_meta" in block else ""
        out.append({"id": mid, "canal": chan, "publicado_utc": tm.group(1) if tm else None,
                    "editado": "edited" in meta[:400], "texto": _clean(tx.group(1)) if tx else ""})
    return out


def _last_id(state: Path) -> int:
    try:
        return int(json.loads(state.read_text(encoding="utf-8"))["ultimo_id"])
    except (OSError, ValueError, KeyError):
        return 0


def capture(channel: str, root: Path = ROOT, max_pages: int = 40, session=None, now: str | None = None) -> int:
    """Guarda los mensajes nuevos de `channel` (desde el último capturado). Devuelve cuántos guardó."""
    s = session or requests.Session()
    folder = Path(root) / channel
    state = folder / "ultimo.json"
    last = _last_id(state)
    new: dict[int, dict] = {}
    before = None
    for _ in range(max_pages):
        url = URL.format(c=channel) + (f"?before={before}" if before else "")
        r = s.get(url, headers=UA, timeout=30)
        if r.status_code != 200:
            break
        posts = parse_page(r.text)
        if not posts:
            break
        for p in posts:
            if p["id"] > last:
                new[p["id"]] = p
        oldest = min(p["id"] for p in posts)
        if oldest <= last + 1 or last == 0:  # primera vez: solo la página más reciente
            break
        before = oldest
        time.sleep(1.0)
    if not new:
        return 0
    stamp = now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    folder.mkdir(parents=True, exist_ok=True)
    for mid in sorted(new):
        p = {**new[mid], "capturado_utc": stamp}
        day = (p["publicado_utc"] or stamp)[:10]
        with open(folder / f"{day}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    state.write_text(json.dumps({"ultimo_id": max(new), "actualizado": stamp}), encoding="utf-8")
    return len(new)


def channels(path: Path = LISTA) -> dict[str, float | None]:
    """{canal: zona horaria en horas (o None si no se conoce)} de la lista vigilada."""
    out = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"([A-Za-z0-9_]{4,64})(?:\s+([+-]?\d+(?:\.\d+)?))?", ln.split("#")[0].strip())
        if m:
            out[m.group(1)] = float(m.group(2)) if m.group(2) else None
    return out


def capture_all(path: Path = LISTA, root: Path = ROOT, log=print) -> dict:
    s = requests.Session()
    out = {}
    for c in channels(path):
        try:
            out[c] = capture(c, root, session=s)
        except requests.RequestException as exc:
            out[c] = f"error: {exc.__class__.__name__}"
        log(f"{c}: {out[c]}")
    return out
