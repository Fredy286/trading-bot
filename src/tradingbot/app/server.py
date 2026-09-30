"""Servidor del panel con la biblioteca estándar (sin dependencias adicionales).

Rutas:
  GET  /               panel HTML
  GET  /api/state      estado del bucle de alertas + veredicto de la investigación
  GET  /api/research   informes markdown de las etapas disponibles
  POST /api/ack        {"alert_id": "..."} → registra la hora de recepción de la alerta
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

from ..timeutil import utcnow

MAX_BODY = 4096


def research_verdict(results_dir: Path, frozen_path: Path = Path("config/frozen.json")) -> dict:
    out: dict = {"available": False}
    if frozen_path.exists():
        fz = json.loads(frozen_path.read_text())
        out.update({"available": True, "verdict": fz.get("verdict"), "candidates": fz.get("candidates", []),
                    "git_sha": fz.get("git_sha"), "config_hash": fz.get("config_hash")})
    for stage in ("dev", "holdout"):
        p = Path(results_dir) / stage / "summary.md"
        out[f"{stage}_summary"] = p.exists()
    return out


def make_handler(runtime_dir: Path, results_dir: Path):
    runtime_dir, results_dir = Path(runtime_dir), Path(results_dir)

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
            self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode(), "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                html = resources.files("tradingbot.app").joinpath("static/index.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if self.path == "/api/state":
                p = runtime_dir / "state.json"
                state = json.loads(p.read_text()) if p.exists() else {"alerts": [], "counts": {},
                                                                     "missing": True}
                state["research"] = research_verdict(results_dir)
                state["server_time"] = utcnow().isoformat()
                return self._json(200, state)
            if self.path == "/api/research":
                docs = {}
                for stage in ("dev", "holdout"):
                    p = results_dir / stage / "summary.md"
                    if p.exists():
                        docs[stage] = p.read_text()
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
            except (ValueError, KeyError):
                return self._json(400, {"error": "JSON inválido"})
            now = utcnow().isoformat()
            state_p = runtime_dir / "state.json"
            found = False
            if state_p.exists():
                state = json.loads(state_p.read_text())
                for a in state.get("alerts", []):
                    if a.get("alert_id") == alert_id:
                        a["received_at"] = a.get("received_at") or now
                        found = True
                if found:
                    tmp = runtime_dir / "state.json.tmp"
                    tmp.write_text(json.dumps(state, ensure_ascii=False))
                    tmp.replace(state_p)
            if not found:
                return self._json(404, {"error": "alerta no encontrada"})
            with open(runtime_dir / "events.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"event": "received", "time": now, "alert_id": alert_id,
                                     "channel": "panel"}) + "\n")
            return self._json(200, {"ok": True, "received_at": now})

    return Handler


def make_server(host: str, port: int, runtime_dir: Path, results_dir: Path) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(runtime_dir, results_dir))


def serve(host: str = "127.0.0.1", port: int = 8765, runtime_dir: Path = Path("runtime/demo"),
          results_dir: Path = Path("results")) -> None:
    srv = make_server(host, port, runtime_dir, results_dir)
    print(f"Panel en http://{host}:{port}  (Ctrl+C para salir) — leyendo {runtime_dir}/state.json")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
