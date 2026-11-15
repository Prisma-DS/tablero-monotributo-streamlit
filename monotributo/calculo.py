"""Cálculos del tablero: facturación de los últimos 12 meses y su estado."""
from dataclasses import dataclass

import pandas as pd

UMBRAL_ATENCION = 0.75
UMBRAL_ALERTA = 0.90


def ventana_12_meses(fecha_corte) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Devuelve (primer día, último día) de los 12 meses que terminan en el mes de la fecha de corte."""
    fin = pd.Timestamp(fecha_corte).normalize() + pd.offsets.MonthEnd(0)
    inicio = (fin - pd.DateOffset(months=11)).replace(day=1)
    return inicio, fin


def facturacion_mensual(df: pd.DataFrame, fecha_corte) -> pd.Series:
    """Facturación neta (facturas + débitos - créditos) por mes dentro de la ventana, con ceros en meses sin movimiento."""
    inicio, fin = ventana_12_meses(fecha_corte)
    en_ventana = df[(df["fecha"] >= inicio) & (df["fecha"] < fin + pd.Timedelta(days=1))]
    meses = pd.period_range(inicio, fin, freq="M")
    por_mes = en_ventana.groupby(en_ventana["fecha"].dt.to_period("M"))["importe"].sum()
    return por_mes.reindex(meses, fill_value=0.0)


def categoria_para(monto: float, escalas: pd.DataFrame) -> str | None:
    """Primera categoría cuyo tope cubre el monto, o None si supera la K."""
    aptas = escalas[escalas["tope_anual"] >= monto]
    return None if aptas.empty else str(aptas.iloc[0]["categoria"])


def estado_de(uso: float) -> str:
    if uso > 1:
        return "Superado"
    if uso >= UMBRAL_ALERTA:
        return "Alerta"
    if uso >= UMBRAL_ATENCION:
        return "Atención"
    return "En rango"


@dataclass(frozen=True)
class Resumen:
    acumulado: float
    promedio_mensual: float
    categoria_actual: str
    tope_actual: float
    uso: float
    margen: float
    categoria_sugerida: str | None
    estado: str
    excluido: bool


def resumen_cliente(df: pd.DataFrame, escalas: pd.DataFrame, categoria_actual: str, fecha_corte) -> Resumen:
    fila = escalas[escalas["categoria"] == categoria_actual]
    if fila.empty:
        raise ValueError(f"Categoría desconocida: {categoria_actual}")
    tope = float(fila.iloc[0]["tope_anual"])

    mensual = facturacion_mensual(df, fecha_corte)
    acumulado = float(mensual.sum())
    return Resumen(
        acumulado=acumulado,
        promedio_mensual=acumulado / 12,
        categoria_actual=categoria_actual,
        tope_actual=tope,
        uso=acumulado / tope,
        margen=tope - acumulado,
        categoria_sugerida=categoria_para(acumulado, escalas),
        estado=estado_de(acumulado / tope),
        excluido=acumulado > float(escalas["tope_anual"].max()),
    )


@dataclass(frozen=True)
class Proyeccion:
    ritmo_mensual: float
    acumulado_proyectado: pd.Series  # facturación de 12 meses móviles, para cada uno de los próximos 12 meses
    meses_hasta_superar: int | None  # primer mes futuro en que supera el tope de la categoría actual
    mes_superacion: pd.Period | None
    mes_exclusion: pd.Period | None  # primer mes futuro en que supera el tope de la categoría K
    maximo_mensual: float  # facturación mensual máxima que no supera el tope durante el horizonte
    horizonte: int


def proyeccion(
    mensual: pd.Series, tope: float, tope_maximo: float, meses_ritmo: int = 3, horizonte: int = 6
) -> Proyeccion:
    """Proyecta la ventana de 12 meses móviles suponiendo que cada mes futuro se factura el
    promedio de los últimos `meses_ritmo` meses.

    En el mes k futuro, la ventana conserva los últimos (12 - k) meses reales y suma k meses
    al ritmo supuesto. `maximo_mensual` es el mayor monto mensual constante que mantiene la
    ventana dentro del tope en cada uno de los próximos `horizonte` meses.
    """
    valores = [float(v) for v in mensual.values]
    n = len(valores)
    if not 1 <= meses_ritmo <= n:
        raise ValueError("meses_ritmo debe estar entre 1 y la cantidad de meses de la ventana")
    if not 1 <= horizonte <= n:
        raise ValueError("horizonte debe estar entre 1 y la cantidad de meses de la ventana")

    ritmo = sum(valores[-meses_ritmo:]) / meses_ritmo
    futuros = pd.period_range(mensual.index[-1] + 1, periods=n, freq="M")
    acumulado = [sum(valores[k:]) + ritmo * k for k in range(1, n + 1)]

    def primer_exceso(limite: float) -> int | None:
        return next((k for k, valor in enumerate(acumulado, start=1) if valor > limite), None)

    k_categoria = primer_exceso(tope)
    k_exclusion = primer_exceso(tope_maximo)
    maximo = min((tope - sum(valores[j:])) / j for j in range(1, horizonte + 1))

    return Proyeccion(
        ritmo_mensual=ritmo,
        acumulado_proyectado=pd.Series(acumulado, index=futuros),
        meses_hasta_superar=k_categoria,
        mes_superacion=futuros[k_categoria - 1] if k_categoria else None,
        mes_exclusion=futuros[k_exclusion - 1] if k_exclusion else None,
        maximo_mensual=max(maximo, 0.0),
        horizonte=horizonte,
    )
