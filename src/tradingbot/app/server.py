"""Servidor del panel con la biblioteca estándar (sin dependencias adicionales).

Rutas:
  GET  /               panel HTML
  GET  /api/state      estado del bucle de alertas + veredicto de la investigación
  GET  /api/research   informes markdown de las etapas disponibles
  POST /api/ack        {"alert_id": "..."} → registra la hora de recepción de la alerta
  GET  /senales        panel del modo de señales anticipadas (cuenta demo, Estudio 16)
  GET  /api/senal/state     estado del bucle de señales, diario y resumen
  POST /api/senal/clic      {"alert_id"} → hora del clic (en hora de Binance)
  POST /api/senal/registro  {"alert_id", "entrada", "salida", "pago", "resultado"} → datos de la plataforma
  GET  /nocturna       panel de la reversión nocturna en divisas (cuenta demo, Estudios 25/27/28)
  GET  /api/nocturna/state  estado del bucle nocturno, diario y resumen
  POST /api/nocturna/clic   {"alert_id"} → hora del clic (en hora de Deriv)

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


def _num(v, lo: float = 0.0, hi: float = 10**7) -> float | None:
    if v in (None, ""):
        return None
    x = float(v)
    if not lo <= x <= hi:
        raise ValueError("fuera de rango")
    return x


def make_handler(runtime_dir: Path, results_dir: Path, senal_dir: Path = Path("runtime/senales"),
                 nocturna_dir: Path = Path("runtime/nocturna")):
    runtime_dir, results_dir, senal_dir = Path(runtime_dir), Path(results_dir), Path(senal_dir)
    nocturna_dir = Path(nocturna_dir)
    ack_lock = threading.Lock()
    senal_lock = threading.Lock()
    nocturna_lock = threading.Lock()

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
            if self.path == "/senales":
                html = resources.files("tradingbot.app").joinpath("static/senales.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if self.path == "/api/senal/state":
                from ..live import anticipada

                try:
                    st = _read_state(senal_dir / "state.json") or {"missing": True}
                except OSError:
                    return self._json(503, {"error": "estado ocupado, reintente"})
                st["diario"] = anticipada.diario(senal_dir)
                st["resumen"] = anticipada.resumen(senal_dir)
                st["server_time"] = utcnow().isoformat()
                return self._json(200, st)
            if self.path == "/nocturna":
                html = resources.files("tradingbot.app").joinpath("static/nocturna.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if self.path == "/api/nocturna/state":
                from ..live import nocturna

                try:
                    st = _read_state(nocturna_dir / "state.json") or {"missing": True}
                except OSError:
                    return self._json(503, {"error": "estado ocupado, reintente"})
                st["diario"] = nocturna.diario(nocturna_dir)
                st["resumen"] = nocturna.resumen(nocturna_dir)
                st["server_time"] = utcnow().isoformat()
                return self._json(200, st)
            if self.path == "/api/research":
                docs = {}
                for stage in ("dev", "holdout"):
                    p = results_dir / stage / "summary.md"
                    if p.exists():
                        docs[stage] = p.read_text(encoding="utf-8")
                return self._json(200, docs)
            return self._json(404, {"error": "no encontrado"})

        def _body(self) -> dict | None:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY:
                return None
            try:
                data = json.loads(self.rfile.read(n))
            except ValueError:
                return None
            return data if isinstance(data, dict) else None

        def do_POST(self):  # noqa: N802
            if self.path in ("/api/senal/clic", "/api/senal/registro"):
                return self._post_senal()
            if self.path == "/api/nocturna/clic":
                return self._post_nocturna()
            if self.path != "/api/ack":
                return self._json(404, {"error": "no encontrado"})
            data = self._body()
            if data is None or "alert_id" not in data:
                return self._json(400, {"error": "JSON inválido"})
            alert_id = str(data["alert_id"])[:32]
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

        def _post_senal(self):
            from datetime import timedelta

            from ..live.anticipada import RESULTADOS

            now = utcnow()
            data = self._body()
            if data is None or "alert_id" not in data:
                return self._json(400, {"error": "JSON inválido"})
            aid = str(data["alert_id"])[:32]
            rows, _ = read_rows(senal_dir / "senales.jsonl")
            if not any(r.get("evento") == "aviso" and r.get("alert_id") == aid for r in rows):
                return self._json(404, {"error": "aviso no encontrado"})
            if self.path == "/api/senal/clic":
                try:
                    offset = float((_read_state(senal_dir / "state.json") or {}).get("desfase_reloj_s") or 0.0)
                except OSError:
                    offset = 0.0
                with senal_lock:
                    prev = [c for c in read_rows(senal_dir / "clics.jsonl")[0] if c.get("alert_id") == aid]
                    if prev:  # vale el primer clic
                        return self._json(200, {"ok": True, "ya_registrado": True, **prev[0]})
                    row = {"alert_id": aid, "hora_pc": now.isoformat(),
                           "hora_binance": (now + timedelta(seconds=offset)).isoformat()}
                    jsonutil.append_line(senal_dir / "clics.jsonl", json.dumps(row))
                return self._json(200, {"ok": True, **row})
            try:
                row = {"alert_id": aid, "hora": now.isoformat()}
                for k in ("entrada", "salida"):
                    if k in data:
                        row[k] = _num(data[k])
                if "pago" in data:
                    row["pago"] = _num(data["pago"], 0.0, 100.0)
                if "resultado" in data:
                    if data["resultado"] not in RESULTADOS:
                        raise ValueError("resultado inválido")
                    row["resultado"] = data["resultado"]
            except (TypeError, ValueError) as exc:
                return self._json(400, {"error": f"dato inválido: {exc}"})
            with senal_lock:
                jsonutil.append_line(senal_dir / "registros.jsonl", json.dumps(row))
            return self._json(200, {"ok": True})

        def _post_nocturna(self):
            from datetime import timedelta

            now = utcnow()
            data = self._body()
            if data is None or "alert_id" not in data:
                return self._json(400, {"error": "JSON inválido"})
            aid = str(data["alert_id"])[:32]
            rows, _ = read_rows(nocturna_dir / "senales.jsonl")
            if not any(r.get("evento") == "aviso" and r.get("alert_id") == aid for r in rows):
                return self._json(404, {"error": "aviso no encontrado"})
            try:
                offset = float((_read_state(nocturna_dir / "state.json") or {}).get("desfase_reloj_s") or 0.0)
            except OSError:
                offset = 0.0
            with nocturna_lock:
                prev = [c for c in read_rows(nocturna_dir / "clics.jsonl")[0] if c.get("alert_id") == aid]
                if prev:  # vale el primer clic
                    return self._json(200, {"ok": True, "ya_registrado": True, **prev[0]})
                row = {"alert_id": aid, "hora_pc": now.isoformat(),
                       "hora_deriv": (now + timedelta(seconds=offset)).isoformat()}
                jsonutil.append_line(nocturna_dir / "clics.jsonl", json.dumps(row))
            return self._json(200, {"ok": True, **row})

    return Handler


class PanelServer(ThreadingHTTPServer):
    """En Windows, SO_REUSEADDR deja que un segundo `tbot serve` use el mismo puerto sin error y el
    navegador siga viendo el primero. Aquí el puerto es exclusivo: el segundo falla con «en uso»."""

    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(host: str, port: int, runtime_dir: Path, results_dir: Path,
                senal_dir: Path = Path("runtime/senales"), nocturna_dir: Path = Path("runtime/nocturna")):
    return PanelServer((host, port), make_handler(runtime_dir, results_dir, senal_dir, nocturna_dir))


def serve(host: str = "127.0.0.1", port: int = 8765, runtime_dir: Path = Path("runtime/demo"),
          results_dir: Path = Path("results"), senal_dir: Path = Path("runtime/senales"),
          nocturna_dir: Path = Path("runtime/nocturna")) -> int:
    try:
        srv = make_server(host, port, runtime_dir, results_dir, senal_dir, nocturna_dir)
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
