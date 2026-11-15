# Control de Monotributo (Streamlit)

Tablero para estudios contables: el contador sube los CSV de **Mis Comprobantes (emitidos)** de sus clientes monotributistas y ve, por cliente, cuánto facturó en los últimos 12 meses frente al tope de su categoría, con semáforo y categoría sugerida.

Todo se procesa en memoria: la app no guarda los archivos.

## Cómo correrlo

```bash
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Para probar sin datos reales, activá **"Usar datos de ejemplo"** en la barra lateral. Los ejemplos son ficticios y se regeneran con `python data/generar_ejemplos.py`.

Tests de la lógica (no necesitan Streamlit): `pytest`

## Estructura

```
app.py                       # interfaz Streamlit
monotributo/
  escalas.py                 # carga la tabla de categorías
  comprobantes.py            # lee el CSV de Mis Comprobantes
  calculo.py                 # ventana de 12 meses, categoría sugerida, estado
data/
  escalas_monotributo.csv    # topes y cuotas (EDITAR cada semestre)
  generar_ejemplos.py        # genera CSV ficticios
  ejemplos/                  # CSV ficticios de demo
tests/test_monotributo.py
```

## Qué calcula

- Facturación neta de los **12 meses completos** que terminan en el mes de la fecha de corte (facturas y notas de débito suman, notas de crédito restan, recibos se excluyen).
- % del tope de la categoría actual y estado: En rango (menos de 75 %), Atención (75 % o más), Alerta (90 % o más), Superado (más del 100 %).
- Categoría que correspondería por facturación y su cuota mensual.
- **Proyección**: supone que cada mes futuro se factura el promedio de los últimos 3, 6 o 12 meses (se elige en la barra lateral) y calcula en qué mes superaría el tope de su categoría y cuánto podría facturar por mes durante los próximos 6 meses sin superarlo. Es una estimación, no una predicción.
- Exportación del resumen a CSV.

**Límite importante:** solo evalúa ingresos brutos. La categoría también depende de superficie, energía eléctrica consumida y alquileres.

## Mantenimiento

1. **Escalas**: ARCA las actualiza cada semestre. Editá `data/escalas_monotributo.csv` con la tabla oficial y la nueva `vigencia_desde`. Los valores cargados (vigentes desde 01/08/2026) se tomaron de una nota periodística: **verificalos contra la tabla oficial de ARCA** antes de usar la herramienta con clientes.
2. **Formato del CSV**: el lector es tolerante (separador `;` o `,`, decimales con coma o punto, varios nombres de columna), pero hay que **probarlo con un archivo real** de Mis Comprobantes. Los códigos de notas de crédito y recibos están en `monotributo/comprobantes.py` por si hace falta ajustarlos.

## Para publicarlo a clientes

- Alojalo en un servidor tuyo (Streamlit Community Cloud, Render, un VPS, etc.) y compará costos antes de fijar tu precio.
- Poné **autenticación** (usuario y contraseña por estudio) y **HTTPS** antes de exponerlo.
- Mantené el modo "subir y calcular" (sin guardar archivos): evita almacenar datos fiscales de terceros. Si en el futuro guardás datos, revisá las obligaciones de la Ley 25.326 de protección de datos personales.
