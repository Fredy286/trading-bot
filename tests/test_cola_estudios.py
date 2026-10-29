"""La cola solo ejecuta órdenes «tbot research studyNN»."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("cola", Path(__file__).parents[1] / "scripts" / "cola_estudios.py")
cola = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cola)


def test_only_research_commands_are_allowed():
    assert cola.ORDEN.match("tbot research study32")
    for bad in ("tbot research study32; rm -rf /", "bash x.sh", "tbot registro resumen --abrir",
                "tbot research study32 && x"):
        assert not cola.ORDEN.match(bad)


def test_queue_moves_ignored_and_done(tmp_path, monkeypatch):
    f = tmp_path / "cola.txt"
    f.write_text("# x\n[pendientes]\nbash malo.sh\n[hechas]\n", encoding="utf-8")
    monkeypatch.setattr(cola, "COLA", f)
    assert cola.main() == 0
    text = f.read_text(encoding="utf-8")
    assert "[pendientes]\n[hechas]\nbash malo.sh  # IGNORADA" in text
