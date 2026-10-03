"""Especificación de instrumentos (fijada en el protocolo; ver docs/01_informe_investigacion_fase1a.md)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    source: str  # "dukascopy" | "binance"
    point: float  # resolución de precio del proveedor
    pip: float  # tamaño de pip (o unidad de reporte)
    decimal_factor: int  # Dukascopy guarda precios como enteros: precio = entero / factor
    plausible_range: tuple[float, float]  # control de cordura al decodificar
    commission_px: float  # comisión ida y vuelta en unidades de precio (escenario contado)
    commission_bps: float = 0.0  # comisión ida y vuelta en puntos básicos (cripto)
    display: str = ""
    assumed_spread: float = 0.0  # spread SUPUESTO (unidades de precio) para fuentes solo-BID (HistData)

    @property
    def label(self) -> str:
        return self.display or self.symbol


# Comisión FX: 0,7 pips ida y vuelta (≈ 7 USD por lote estándar en cuentas ECN).
# Oro: 0,07 USD/oz ida y vuelta. BTC/USDT: 0,1 % por lado (tarifa taker estándar) = 20 pb.
# Spread supuesto (solo para HistData, que no trae ASK): escenario OPTIMISTA tipo cuenta ECN
# (EUR/USD 0,2 pips; GBP/USD 0,5; USD/JPY 0,3; AUD/USD 0,4; oro 0,25 USD). Los spreads minoristas
# suelen ser mayores; el informe incluye una tabla de sensibilidad del umbral a otros costos.
INSTRUMENTS: dict[str, Instrument] = {
    "EURUSD": Instrument("EURUSD", "dukascopy", 1e-5, 1e-4, 100_000, (0.8, 1.6), 0.7e-4, display="EUR/USD",
                         assumed_spread=0.2e-4),
    "GBPUSD": Instrument("GBPUSD", "dukascopy", 1e-5, 1e-4, 100_000, (0.9, 1.8), 0.7e-4, display="GBP/USD",
                         assumed_spread=0.5e-4),
    "AUDUSD": Instrument("AUDUSD", "dukascopy", 1e-5, 1e-4, 100_000, (0.45, 1.0), 0.7e-4, display="AUD/USD",
                         assumed_spread=0.4e-4),
    "USDJPY": Instrument("USDJPY", "dukascopy", 1e-3, 1e-2, 1_000, (90.0, 200.0), 0.7e-2, display="USD/JPY",
                         assumed_spread=0.3e-2),
    "XAUUSD": Instrument("XAUUSD", "dukascopy", 1e-3, 1e-1, 1_000, (1200.0, 6000.0), 0.07, display="XAU/USD",
                         assumed_spread=0.25),
    "BTCUSDT": Instrument("BTCUSDT", "binance", 1e-2, 1.0, 1, (10_000.0, 250_000.0), 0.0, commission_bps=20.0,
                          display="BTC/USDT"),
    # Añadido para el Estudio 3 (2026-10-03); no forma parte del estudio de la Fase 1B.
    "ETHUSDT": Instrument("ETHUSDT", "binance", 1e-2, 1.0, 1, (300.0, 15_000.0), 0.0, commission_bps=20.0,
                          display="ETH/USDT"),
    # Instrumento sintético SOLO para pruebas y demostraciones (nunca para conclusiones).
    "SYNTH": Instrument("SYNTH", "synthetic", 1e-5, 1e-4, 100_000, (0.1, 10.0), 0.7e-4,
                        display="SINTÉTICO (no real)"),
}


def get_instrument(symbol: str) -> Instrument:
    try:
        return INSTRUMENTS[symbol.upper()]
    except KeyError as exc:  # pragma: no cover - mensaje amigable
        raise KeyError(f"Instrumento desconocido: {symbol}. Disponibles: {', '.join(INSTRUMENTS)}") from exc
