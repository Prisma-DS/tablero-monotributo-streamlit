"""Lectura del CSV de "Mis Comprobantes" (comprobantes emitidos) de ARCA.

El lector es tolerante: detecta el separador (; o ,), acepta decimales con
coma o con punto, y reconoce variantes habituales de los nombres de columna.
Supuestos que conviene validar con un archivo real:
  * El tipo de comprobante viene como código ("11") o "11 - Factura C".
  * Las notas de crédito vienen con importe positivo (se restan igual si
    vinieran en negativo, porque se toma el valor absoluto y se aplica el signo).
  * Los recibos no son ingresos y se excluyen.

Los códigos están en las constantes de abajo, por si hace falta ajustarlos.
"""
import io
import unicodedata

import pandas as pd

NOTAS_DE_CREDITO = {3, 8, 13, 53, 203, 208, 213}
RECIBOS = {4, 9, 15}
MONEDAS_PESO = {"", "$", "PES", "ARS"}

ALIAS_COLUMNAS = {
    "fecha": ["fecha de emision", "fecha"],
    "tipo": ["tipo de comprobante", "tipo"],
    "total": ["imp. total", "importe total", "total"],
    "moneda": ["moneda"],
    "tipo_cambio": ["tipo cambio", "tipo de cambio"],
}
OBLIGATORIAS = ["fecha", "tipo", "total"]


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower()


def _decodificar(contenido: bytes) -> str:
    try:
        return contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenido.decode("latin-1")


def _a_numero(serie: pd.Series) -> pd.Series:
    """Convierte textos como '1.234,56' o '1234.56' a número."""
    s = serie.fillna("").astype(str).str.replace(r"[^\d,.\-]", "", regex=True)
    con_coma = s.str.contains(",", regex=False)
    con_formato_ar = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s.where(~con_coma, con_formato_ar), errors="coerce")


def _a_fecha(serie: pd.Series) -> pd.Series:
    s = serie.fillna("").astype(str).str.strip().str[:10]
    fechas = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    pendientes = fechas.isna()
    if pendientes.any():
        fechas.loc[pendientes] = pd.to_datetime(s[pendientes], format="%d/%m/%Y", errors="coerce")
    return fechas


def leer_comprobantes(contenido: bytes) -> tuple[pd.DataFrame, list[str]]:
    """Lee el CSV y devuelve (comprobantes, avisos).

    El DataFrame tiene las columnas: fecha, codigo, importe (con signo:
    las notas de crédito restan). Lanza ValueError si el archivo no sirve.
    """
    texto = _decodificar(contenido)
    if not texto.strip():
        raise ValueError("El archivo está vacío.")

    encabezado = texto.splitlines()[0]
    separador = ";" if encabezado.count(";") >= encabezado.count(",") else ","
    crudo = pd.read_csv(io.StringIO(texto), sep=separador, dtype=str, keep_default_na=False)

    nombres = {_normalizar(c): c for c in crudo.columns}
    col = {
        clave: next((nombres[o] for o in opciones if o in nombres), None)
        for clave, opciones in ALIAS_COLUMNAS.items()
    }
    faltan = [k for k in OBLIGATORIAS if col[k] is None]
    if faltan:
        raise ValueError(
            f"No encontré las columnas obligatorias: {', '.join(faltan)}. "
            f"Columnas del archivo: {', '.join(crudo.columns)}"
        )

    avisos: list[str] = []
    df = pd.DataFrame(
        {
            "fecha": _a_fecha(crudo[col["fecha"]]),
            "codigo": pd.to_numeric(crudo[col["tipo"]].str.extract(r"(\d+)")[0], errors="coerce"),
            "total": _a_numero(crudo[col["total"]]),
        }
    )

    if col["moneda"] and col["tipo_cambio"]:
        moneda = crudo[col["moneda"]].str.strip().str.upper()
        cambio = _a_numero(crudo[col["tipo_cambio"]])
        extranjera = ~moneda.isin(MONEDAS_PESO) & (cambio > 0)
        if extranjera.any():
            df.loc[extranjera, "total"] = df.loc[extranjera, "total"] * cambio[extranjera]
            avisos.append(f"{int(extranjera.sum())} comprobantes en moneda extranjera convertidos con su tipo de cambio.")

    invalidas = df["fecha"].isna() | df["codigo"].isna() | df["total"].isna()
    if invalidas.any():
        avisos.append(f"Se ignoraron {int(invalidas.sum())} filas con fecha, tipo o importe ilegible.")
    df = df[~invalidas].copy()

    df["codigo"] = df["codigo"].astype(int)
    es_recibo = df["codigo"].isin(RECIBOS)
    if es_recibo.any():
        n= int(es_recibo.sum())
        avisos.append(f"Se {'excluyó' if n == 1 else 'excluyeron'} {n} {'recibo' if n == 1 else 'recibos'} (no son ingresos).")
        #avisos.append(f"Se excluyeron {int(es_recibo.sum())} recibos (no son ingresos).")
    df = df[~es_recibo].copy()

    signo = pd.Series(1.0, index=df.index).where(~df["codigo"].isin(NOTAS_DE_CREDITO), -1.0)
    df["importe"] = df["total"].abs() * signo

    if df.empty:
        raise ValueError("El archivo no tiene comprobantes válidos para calcular.")
    return df[["fecha", "codigo", "importe"]].reset_index(drop=True), avisos
