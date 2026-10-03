"""Servidor del panel con la biblioteca estándar (sin dependencias adicionales).

Rutas:
  GET  /               panel HTML
  GET  /api/state      estado del bucle de alertas + veredicto de la investigación
  GET  /api/research   informes markdown de las etapas disponibles
  POST /api/ack        {"alert_id": "..."} → registra la hora de recepción de la alerta

El panel solo LEE state.json (lo escribe `tbot live`); las confirmaciones de recepción van a
acks.jsonl, que solo escribe este servidor.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

from .. import jsonutil
from ..execution.paper import read_rows
from ..timeutil import utcnow

MAX_BODY = 4096


def research_verdict(results_dir: Path, frozen_path: Path = Path("config/frozen.json")) -> dict:
    out: dict = {"available": False}
    fz: dict = {}
    if frozen_path.exists():
        fz = jsonutil.load(frozen_path)
        out.update({"available": True, "verdict": fz.get("verdict"), "candidates": fz.get("candidates", []),
                    "git_sha": fz.get("git_sha"), "config_hash": fz.get("config_hash")})
    for stage in ("dev", "holdout"):
        p = Path(results_dir) / stage / "summary.md"
        out[f"{stage}_summary"] = p.exists()
    # config/frozen.json se congela ANTES del periodo bloqueado: su veredicto dice «pendiente». Si el
    # periodo bloqueado de ESE MISMO estudio ya se evaluó, su veredicto mecánico es el vigente.
    hv_path = Path(results_dir) / "holdout" / "verdict.json"
    if hv_path.exists():
        hv = jsonutil.load(hv_path)
        if same_study(hv, fz):
            out["holdout_verdict"] = hv.get("verdict")
            out["holdout_passed"] = hv.get("passed", [])
            out["holdout_n_candidates"] = hv.get("n_candidates")
        else:
            out["holdout_other_study"] = True
    return out


def same_study(holdout_verdict: dict, frozen: dict) -> bool:
    """¿El veredicto del periodo bloqueado corresponde a esta configuración congelada? (un estudio nuevo,
    p. ej. con Dukascopy, reescribe config/frozen.json pero no results/holdout)."""
    return (holdout_verdict.get("frozen_git_sha") == frozen.get("git_sha")
            and holdout_verdict.get("config_hash") == frozen.get("config_hash"))


def _read_state(p: Path, tries: int = 5) -> dict | None:
    """Lee state.json; en Windows puede estar ocupado un instante mientras `tbot live` lo reemplaza."""
    for _ in range(tries):
        try:
            return jsonutil.load(p)
        except FileNotFoundError:
            return None
        except (PermissionError, ValueError):  # ocupado o a medio reemplazar: reintento breve
            time.sleep(0.05)
    raise OSError("state.json ocupado")


def first_acks(runtime_dir: Path) -> dict[str, str]:
    """alert_id → hora de la PRIMERA confirmación de recepción."""
    rows, _ = read_rows(Path(runtime_dir) / "acks.jsonl")
    acks: dict[str, str] = {}
    for r in rows:
        if r.get("alert_id") and r.get("time"):
            acks.setdefault(r["alert_id"], r["time"])
    return acks


def make_handler(runtime_dir: Path, results_dir: Path):
    runtime_dir, results_dir = Path(runtime_dir), Path(results_dir)
    ack_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silencio en consola
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, jsonutil.dumps(obj, default=str).encode(), "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                html = resources.files("tradingbot.app").joinpath("static/index.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if self.path == "/api/state":
                try:
                    state = _read_state(runtime_dir / "state.json")
                except OSError:
                    return self._json(503, {"error": "estado ocupado, reintente"})
                if state is None:
                    state = {"alerts": [], "counts": {}, "missing": True}
                acks = first_acks(runtime_dir)
                for a in state.get("alerts", []):
                    a["received_at"] = a.get("received_at") or acks.get(a.get("alert_id"))
                state["research"] = research_verdict(results_dir)
                state["server_time"] = utcnow().isoformat()
                return self._json(200, state)
            if self.path == "/api/research":
                docs = {}
                for stage in ("dev", "holdout"):
                    p = results_dir / stage / "summary.md"
                    if p.exists():
                        docs[stage] = p.read_text(encoding="utf-8")
                return self._json(200, docs)
            return self._json(404, {"error": "no encontrado"})

        def do_POST(self):  # noqa: N802
            if self.path != "/api/ack":
                return self._json(404, {"error": "no encontrado"})
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY:
                return self._json(400, {"error": "cuerpo inválido"})
            try:
                data = json.loads(self.rfile.read(n))
                alert_id = str(data["alert_id"])[:32]
            except (ValueError, KeyError, TypeError):
                return self._json(400, {"error": "JSON inválido"})
            try:
                state = _read_state(runtime_dir / "state.json") or {}
            except OSError:
                return self._json(503, {"error": "estado ocupado, reintente"})
            if not any(a.get("alert_id") == alert_id for a in state.get("alerts", [])):
                return self._json(404, {"error": "alerta no encontrada"})
            with ack_lock:
                prev = first_acks(runtime_dir).get(alert_id)
                if prev:  # un segundo clic no registra otra hora de recepción
                    return self._json(200, {"ok": True, "received_at": prev, "ya_recibida": True})
                now = utcnow().isoformat()
                jsonutil.append_line(runtime_dir / "acks.jsonl", json.dumps(
                    {"event": "received", "time": now, "alert_id": alert_id, "channel": "panel"}))
            return self._json(200, {"ok": True, "received_at": now})

    return Handler


class PanelServer(ThreadingHTTPServer):
    """En Windows, SO_REUSEADDR deja que un segundo `tbot serve` use el mismo puerto sin error y el
    navegador siga viendo el primero. Aquí el puerto es exclusivo: el segundo falla con «en uso»."""

    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(host: str, port: int, runtime_dir: Path, results_dir: Path) -> ThreadingHTTPServer:
    return PanelServer((host, port), make_handler(runtime_dir, results_dir))


def serve(host: str = "127.0.0.1", port: int = 8765, runtime_dir: Path = Path("runtime/demo"),
          results_dir: Path = Path("results")) -> int:
    try:
        srv = make_server(host, port, runtime_dir, results_dir)
    except OSError as exc:
        print(f"No se pudo abrir el panel en {host}:{port} ({exc}). ¿Hay otro «tbot serve» abierto? "
              "Ciérrelo o use otro puerto con --port.")
        return 2
    print(f"Panel en http://{host}:{port}  (Ctrl+C para salir) — leyendo {Path(runtime_dir) / 'state.json'}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
