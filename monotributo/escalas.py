"""Carga de la tabla de categorías del Monotributo.

Los valores viven en data/escalas_monotributo.csv para poder actualizarlos
cada semestre sin tocar el código.
"""
from pathlib import Path

import pandas as pd

RUTA_ESCALAS = Path(__file__).resolve().parent.parent / "data" / "escalas_monotributo.csv"
COLUMNAS = ["categoria", "tope_anual", "cuota_servicios", "cuota_bienes", "vigencia_desde"]


def cargar_escalas(ruta: Path = RUTA_ESCALAS) -> pd.DataFrame:
    """Devuelve las categorías ordenadas de menor a mayor tope anual."""
    df = pd.read_csv(ruta, dtype={"categoria": str}, parse_dates=["vigencia_desde"])
    faltantes = [c for c in COLUMNAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en {ruta.name}: {', '.join(faltantes)}")
    return df.sort_values("tope_anual").reset_index(drop=True)
