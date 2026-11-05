"""Escribe el proyecto de Power BI (PBIP: modelo en TMDL + reporte en PBIR) sobre ../datos/.

Se vuelve a correr cuando cambian las medidas o las páginas. La ruta de los CSV queda en el
parámetro RutaDatos del modelo (Transformar datos > Parámetros) por si la carpeta se mueve.
"""
import json
import sys
import os
import uuid

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
DATOS = os.path.join(RAIZ, "datos") + os.sep
NOMBRE = "InventarioCEDIS"
# origen del modelo: PostgreSQL (sql/construir.ps1) o, con --csv, los archivos de datos/
FUENTE = "csv" if "--csv" in sys.argv else "postgres"
SERVIDOR, BASE = "localhost:5433", "inventario_cedis"
PARAMETROS = ["Servidor", "BaseDatos"] if FUENTE == "postgres" else ["RutaDatos"]
NS = uuid.UUID("2f1b7a52-5c0e-4a5e-9d0a-6c1f0e7b3a11")
tag = lambda *p: str(uuid.uuid5(NS, "/".join(p)))

# ---------------------------------------------------------------- modelo
TABLAS = {
    "dim_fecha": {"csv": "dim_fecha.csv", "fecha_tabla": True, "cols": [
        ("fecha", "dateTime", {"key": True}), ("anio", "int64", {}), ("mes", "int64", {}),
        ("anio_mes", "string", {}), ("nombre_mes", "string", {"sort": "mes"}),
        ("dia_semana", "int64", {}), ("nombre_dia", "string", {"sort": "dia_semana"}),
        ("es_fin_de_semana", "boolean", {})]},
    "dim_almacen": {"csv": "dim_almacen.csv", "cols": [
        ("almacen", "string", {"key": True}), ("nombre", "string", {}), ("estado", "string", {})]},
    "dim_producto": {"csv": "dim_producto.csv", "cols": [
        ("sku", "string", {"key": True}), ("producto", "string", {}), ("categoria", "string", {}),
        ("cliente", "string", {})]},
    "fct_movimiento": {"csv": "fct_movimiento.csv", "cols": [
        ("fecha", "dateTime", {}), ("almacen", "string", {}), ("sku", "string", {}),
        ("tipo", "string", {}), ("cantidad", "int64", {})]},
    "fct_existencia_diaria": {"csv": "fct_existencia_diaria.csv", "cols": [
        ("fecha", "dateTime", {}), ("almacen", "string", {}), ("sku", "string", {}),
        ("existencia", "int64", {}), ("en_cero", "boolean", {}), ("venta_perdida_est", "double", {})]},
    "fct_validacion": {"csv": "fct_validacion.csv", "cols": [
        ("almacen", "string", {}), ("sku", "string", {}), ("conteo", "int64", {}),
        ("reconstruido", "int64", {}), ("diferencia", "int64", {}),
        ("coincide_exacto", "boolean", {}), ("coincide_cero", "boolean", {})]},
}
M_TIPO = {"dateTime": "type date", "int64": "Int64.Type", "string": "type text",
          "boolean": "type logical", "double": "type number"}
FORMATO = {"dateTime": "yyyy-mm-dd", "int64": "#,0", "double": "#,0.00"}

RELACIONES = [
    ("fct_movimiento", "fecha", "dim_fecha", "fecha"),
    ("fct_movimiento", "almacen", "dim_almacen", "almacen"),
    ("fct_movimiento", "sku", "dim_producto", "sku"),
    ("fct_existencia_diaria", "fecha", "dim_fecha", "fecha"),
    ("fct_existencia_diaria", "almacen", "dim_almacen", "almacen"),
    ("fct_existencia_diaria", "sku", "dim_producto", "sku"),
    ("fct_validacion", "almacen", "dim_almacen", "almacen"),
    ("fct_validacion", "sku", "dim_producto", "sku"),
]

MEDIDAS = [
    # nombre, expresión DAX, formato, carpeta
    ("Existencia (u)", "CALCULATE ( SUM ( fct_existencia_diaria[existencia] ), LASTDATE ( dim_fecha[fecha] ) )", "#,0", "Existencias"),
    ("Días-producto", "COUNTROWS ( fct_existencia_diaria )", "#,0", "Existencias"),
    ("Días en cero", "CALCULATE ( COUNTROWS ( fct_existencia_diaria ), fct_existencia_diaria[en_cero] = TRUE () )", "#,0", "Existencias"),
    ("Disponibilidad", "DIVIDE ( [Días-producto] - [Días en cero], [Días-producto] )", "0.0%", "Existencias"),
    ("Productos en cero (último día)", "CALCULATE ( [Días en cero], LASTDATE ( dim_fecha[fecha] ) )", "#,0", "Existencias"),
    ("Venta perdida estimada (u)", "SUM ( fct_existencia_diaria[venta_perdida_est] )", "#,0", "Existencias"),
    ("Entradas (u)", "CALCULATE ( SUM ( fct_movimiento[cantidad] ), fct_movimiento[tipo] = \"Entrada\" )", "#,0", "Movimientos"),
    ("Salidas (u)", "- CALCULATE ( SUM ( fct_movimiento[cantidad] ), fct_movimiento[tipo] = \"Salida\" )", "#,0", "Movimientos"),
    ("Líneas de movimiento", "COUNTROWS ( fct_movimiento )", "#,0", "Movimientos"),
    ("Ajustes netos (u)", "CALCULATE ( SUM ( fct_movimiento[cantidad] ), fct_movimiento[tipo] IN { \"Ajuste merma\", \"Ajuste conteo\" } )", "#,0", "Movimientos"),
    ("Venta diaria 30 d (u)",
     "VAR fin = MAX ( dim_fecha[fecha] )\n"
     "RETURN DIVIDE ( - CALCULATE ( SUM ( fct_movimiento[cantidad] ), fct_movimiento[tipo] = \"Salida\", "
     "DATESINPERIOD ( dim_fecha[fecha], fin, -30, DAY ) ), 30 )", "#,0.0", "Movimientos"),
    ("Días de cobertura", "DIVIDE ( [Existencia (u)], [Venta diaria 30 d (u)] )", "#,0.0", "Movimientos"),
    ("Pares validados", "COUNTROWS ( fct_validacion )", "#,0", "Validación"),
    ("Coincidencia exacta", "DIVIDE ( CALCULATE ( COUNTROWS ( fct_validacion ), fct_validacion[coincide_exacto] = TRUE () ), [Pares validados] )", "0.0%", "Validación"),
    ("Acierto en cero", "DIVIDE ( CALCULATE ( COUNTROWS ( fct_validacion ), fct_validacion[coincide_cero] = TRUE () ), [Pares validados] )", "0.0%", "Validación"),
    ("Error medio (u)", "AVERAGEX ( fct_validacion, ABS ( fct_validacion[diferencia] ) )", "#,0.00", "Validación"),
    ("Conteo físico (u)", "SUM ( fct_validacion[conteo] )", "#,0", "Validación"),
    ("Reconstruido (u)", "SUM ( fct_validacion[reconstruido] )", "#,0", "Validación"),
]


def q(nombre):
    """Nombre TMDL: entre comillas simples si no es un identificador simple."""
    return nombre if nombre.replace("_", "").isalnum() and nombre.isascii() else "'" + nombre.replace("'", "''") + "'"


def tabla_tmdl(nombre, t):
    out = [f"table {nombre}", f"\tlineageTag: {tag('t', nombre)}"]
    if t.get("fecha_tabla"):
        out.append("\tdataCategory: Time")
    out.append("")
    for c, tipo, op in t["cols"]:
        out.append(f"\tcolumn {c}")
        out.append(f"\t\tdataType: {tipo}")
        if nombre.startswith("fct_") and c in ("fecha", "almacen", "sku"):
            out.append("\t\tisHidden")  # se filtra por las dimensiones, no por la llave del hecho
        if op.get("key"):
            out.append("\t\tisKey")
        if tipo in FORMATO:
            out.append(f"\t\tformatString: {FORMATO[tipo]}")
        out.append(f"\t\tlineageTag: {tag('c', nombre, c)}")
        out.append("\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {c}")
        if op.get("sort"):
            out.append(f"\t\tsortByColumn: {op['sort']}")
        if tipo == "dateTime":
            out += ["", "\t\tannotation UnderlyingDateTimeDataType = Date"]
        out.append("")
    tipos = ", ".join("{" + f'"{c}", {M_TIPO[tp]}' + "}" for c, tp, _ in t["cols"])
    if FUENTE == "postgres":
        m = ["\t\t\t\tlet",
             "\t\t\t\t    Origen = PostgreSQL.Database(Servidor, BaseDatos),",
             f'\t\t\t\t    Tabla = Origen{{[Schema = "pbi", Item = "{nombre}"]}}[Data]',
             "\t\t\t\tin", "\t\t\t\t    Tabla"]
    else:
        m = ["\t\t\t\tlet",
             f'\t\t\t\t    Origen = Csv.Document(File.Contents(RutaDatos & "{t["csv"]}"), [Delimiter = ",", Columns = {len(t["cols"])}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
             "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),",
             f'\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos}}}, "en-US")',
             "\t\t\t\tin", "\t\t\t\t    Tipos"]
    out += [f"\tpartition {nombre} = m", "\t\tmode: import", "\t\tsource ="] + m + [""]
    return "\n".join(out) + "\n"


def medidas_tmdl():
    out = ["table _Medidas", f"\tlineageTag: {tag('t', '_Medidas')}", ""]
    for n, expr, fmt, carpeta in MEDIDAS:
        lineas = expr.split("\n")
        if len(lineas) == 1:
            out.append(f"\tmeasure {q(n)} = {expr}")
        else:
            out.append(f"\tmeasure {q(n)} =")
            out += ["\t\t\t" + l for l in lineas]
        out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tdisplayFolder: {carpeta}")
        out.append(f"\t\tlineageTag: {tag('m', n)}")
        out.append("")
    out += ["\tcolumn Value", "\t\tisHidden", "\t\tformatString: 0", f"\t\tlineageTag: {tag('c', '_Medidas', 'Value')}",
            "\t\tsummarizeBy: none", "\t\tisNameInferred", "\t\tsourceColumn: [Value]", "",
            "\tpartition _Medidas = calculated", "\t\tmode: import", "\t\tsource = {BLANK()}", ""]
    return "\n".join(out) + "\n"


def escribir(ruta, texto):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def jdump(ruta, obj):
    escribir(ruta, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def construir_modelo(base):
    d = os.path.join(base, "definition")
    escribir(os.path.join(d, "database.tmdl"), "database\n\tcompatibilityLevel: 1606\n\n")
    orden = list(TABLAS) + PARAMETROS
    modelo = ["model Model", "\tculture: es-MX", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
              "\tsourceQueryCulture: es-MX", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
              "annotation PBI_QueryOrder = " + json.dumps(orden, ensure_ascii=False), "",
              "annotation __PBI_TimeIntelligenceEnabled = 0", "",
              'annotation PBI_ProTooling = ["DevMode"]', ""]
    modelo += [f"ref table {t}" for t in list(TABLAS) + ["_Medidas"]]
    if os.path.exists(os.path.join(d, "cultures", "es-MX.tmdl")):
        modelo += ["", "ref cultureInfo es-MX"]
    escribir(os.path.join(d, "model.tmdl"), "\n".join(modelo) + "\n\n")
    # parámetros del origen: Servidor y BaseDatos (PostgreSQL) o RutaDatos (CSV)
    def parametro(n, valor):
        return (f'expression {n} = "{valor}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
                f"\tlineageTag: {tag('e', n)}\n\n\tannotation PBI_ResultType = Text\n\n")
    if FUENTE == "postgres":
        exp = parametro("Servidor", SERVIDOR) + parametro("BaseDatos", BASE)
    else:
        exp = parametro("RutaDatos", DATOS)  # en M la diagonal invertida no escapa nada
    escribir(os.path.join(d, "expressions.tmdl"), exp)
    rel = []
    for ft, fc, tt, tc in RELACIONES:
        rel += [f"relationship {tag('r', ft, fc, tt)}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    escribir(os.path.join(d, "relationships.tmdl"), "\n".join(rel) + "\n")
    for n, t in TABLAS.items():
        escribir(os.path.join(d, "tables", f"{n}.tmdl"), tabla_tmdl(n, t))
    escribir(os.path.join(d, "tables", "_Medidas.tmdl"), medidas_tmdl())
    jdump(os.path.join(base, "definition.pbism"), {"version": "4.2", "settings": {}})
    jdump(os.path.join(base, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": tag("logical", "model")}})


# ---------------------------------------------------------------- reporte
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"
PG = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"


def col(ent, prop, nombre=None):
    p = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}},
         "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if nombre:
        p["displayName"] = nombre
    return p


def med(prop):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": prop}},
            "queryRef": f"_Medidas.{prop}", "nativeQueryRef": prop}


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def visual(nombre, tipo, pos, roles, titulo, alt, z, orden=None):
    x, y, w, h = pos
    v = {"visualType": tipo, "query": {"queryState": roles}, "drillFilterOtherVisuals": True,
         "visualContainerObjects": {
             "title": [{"properties": {"show": lit("true"), "text": lit("'" + titulo.replace("'", "''") + "'")}}],
             "general": [{"properties": {"altText": lit("'" + alt.replace("'", "''") + "'")}}]}}
    if orden:
        f, sentido = orden
        v["query"]["sortDefinition"] = {"sort": [{"field": f["field"], "direction": sentido}], "isDefaultSort": True}
    return {"$schema": VC, "name": nombre,
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z * 1000},
            "visual": v}


def tarjeta(nombre, medida, pos, titulo, alt, z):
    return visual(nombre, "card", pos, {"Values": {"projections": [med(medida)]}}, titulo, alt, z)


def proj(*ps, activo=False):
    ps = list(ps)
    if activo:
        ps[0] = dict(ps[0], active=True)
    return {"projections": ps}


# ---- identidad visual: la misma del portafolio (concreto, amarillo de seguridad, acero)
TINTA, GRIS, LINEA, PANEL, FONDO, MARCO = "#1B232B", "#56616B", "#D3D8D3", "#FBFCFA", "#EEF0EC", "#E2E5E0"
ACERO, AMBAR, AMBAR_TXT, ACERO_CLARO = "#2F5D7C", "#E3A200", "#7D5600", "#9DB7C9"
BIEN, MAL = "#2B7A4B", "#B0362C"
NOMBRE_TEMA = "InventarioCEDIS_tema.json"


def solido(c):
    return {"solid": {"color": c}}


TEMA = {
    "name": "Inventario CEDIS",
    "dataColors": [ACERO, AMBAR, ACERO_CLARO, TINTA, BIEN, MAL, "#7D8A94", "#C9A55A"],
    "background": "#FFFFFF", "foreground": TINTA, "tableAccent": AMBAR,
    "good": BIEN, "bad": MAL, "neutral": AMBAR,
    "maximum": ACERO, "center": "#F3F5F2", "minimum": MAL,
    "textClasses": {
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": TINTA},
        "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": TINTA},
        "header": {"fontSize": 10, "fontFace": "Segoe UI Semibold", "color": TINTA},
        "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": GRIS},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": solido(PANEL), "transparency": 0}],
            "border": [{"show": True, "color": solido(LINEA), "radius": 6}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": 8, "bottom": 10, "left": 12, "right": 12}],
            "title": [{"show": True, "fontColor": solido(TINTA), "fontSize": 11,
                       "fontFamily": "Segoe UI Semibold", "alignment": "left"}],
            "visualHeader": [{"show": True, "foreground": solido(GRIS), "border": solido(PANEL), "background": solido(PANEL)}],
            "categoryAxis": [{"showAxisTitle": False, "labelColor": solido(GRIS), "fontSize": 9, "gridlineShow": False}],
            "valueAxis": [{"showAxisTitle": False, "labelColor": solido(GRIS), "fontSize": 9,
                           "gridlineShow": True, "gridlineColor": solido("#E3E6E2"), "gridlineStyle": "solid"}],
            "legend": [{"show": True, "position": "Top", "labelColor": solido(GRIS), "fontSize": 9}],
        }},
        "page": {"*": {
            "background": [{"color": solido(FONDO), "transparency": 0}],
            "outspace": [{"color": solido(MARCO), "transparency": 0}],
        }},
        "card": {"*": {
            "labels": [{"color": solido(TINTA), "fontSize": 26, "fontFamily": "Segoe UI Semibold", "labelDisplayUnits": 1}],
            "categoryLabels": [{"show": False}],
            "title": [{"show": True, "fontColor": solido(GRIS), "fontSize": 9, "fontFamily": "Segoe UI"}],
            "border": [{"show": True, "color": solido(LINEA), "radius": 6}],
        }},
        "textbox": {"*": {
            "background": [{"show": False}], "border": [{"show": False}], "title": [{"show": False}],
            "visualHeader": [{"show": False}], "padding": [{"top": 0, "bottom": 0, "left": 0, "right": 0}],
        }},
        "slicer": {"*": {
            "title": [{"show": False}],
            "header": [{"show": False}],
            "items": [{"fontColor": solido(TINTA), "textSize": 10}],
        }},
        "tableEx": {"*": {
            "columnHeaders": [{"fontColor": solido("#FFFFFF"), "backColor": solido(TINTA), "fontFamily": "Segoe UI Semibold", "fontSize": 10}],
            "values": [{"fontColor": solido(TINTA), "backColor": solido(PANEL), "backColorSecondary": solido("#F3F5F2"), "fontSize": 10}],
            "total": [{"fontColor": solido(TINTA), "backColor": solido("#E9ECE8")}],
            "grid": [{"gridHorizontal": True, "gridHorizontalColor": solido("#E3E6E2"), "gridVertical": False,
                      "outlineColor": solido(LINEA), "rowPadding": 4}],
        }},
        "lineChart": {"*": {"lineStyles": [{"strokeWidth": 2, "showMarker": False}]}},
        "clusteredBarChart": {"*": {"labels": [{"show": True, "color": solido(TINTA), "fontSize": 9, "labelDisplayUnits": 1}],
                                     "valueAxis": [{"show": False}]}},
        "scatterChart": {"*": {"bubbles": [{"bubbleSize": -6}], "dataPoint": [{"defaultColor": solido(ACERO)}]}},
    },
}

# ---- rejilla: página de 1280 × 720, margen de 16 px, separación de 12 px
M, G, ANCHO = 16, 12, 1280
UTIL = ANCHO - 2 * M
ENC_Y, ENC_H = 10, 54
TAR_Y, TAR_H = 72, 92
CUERPO_Y = TAR_Y + TAR_H + G   # 176
FONDO_Y = 720 - M              # 704


def cuarto(i):
    w = (UTIL - 3 * G) / 4
    return round(M + i * (w + G)), round(w)


def texto(nombre, pos, parrafos, alt, z):
    """Cuadro de texto: cada párrafo es (alineación, [(texto, estilo), ...])."""
    x, y, w, h = pos
    ps = []
    for alin, corridas in parrafos:
        p = {"textRuns": [{"value": t, "textStyle": st} for t, st in corridas]}
        if alin != "left":
            p["horizontalTextAlignment"] = alin
        ps.append(p)
    return {"$schema": VC, "name": nombre,
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": (z - 90) * 10},
            "visual": {"visualType": "textbox",
                       "objects": {"general": [{"properties": {"paragraphs": ps}}]},
                       "visualContainerObjects": {"general": [{"properties": {"altText": lit("'" + alt.replace("'", "''") + "'")}}]},
                       "drillFilterOtherVisuals": True}}


CEJA = {"fontFamily": "Segoe UI Semibold", "fontSize": "9pt", "color": AMBAR_TXT}
TIT = {"fontFamily": "Segoe UI Semibold", "fontSize": "20pt", "color": TINTA}
SUB = {"fontFamily": "Segoe UI", "fontSize": "10pt", "color": GRIS}
DER = {"fontFamily": "Segoe UI", "fontSize": "9pt", "color": GRIS}


def encabezado(pagina, titulo, subtitulo):
    return [
        texto(f"h_{pagina}", (M, ENC_Y, 860, ENC_H),
              [("left", [("INVENTARIO CEDIS  ·  DATOS SINTÉTICOS", CEJA)]),
               ("left", [(titulo, TIT), ("   " + subtitulo, SUB)])],
              f"Encabezado de la página {titulo}: {subtitulo}", 90),
        texto(f"h_{pagina}_meta", (ANCHO - M - 360, ENC_Y + 8, 360, ENC_H - 8),
              [("right", [("4 CEDIS  ·  120 productos", DER)]),
               ("right", [("1 sep 2025 – 4 nov 2026  ·  conteo físico al 23 oct 2026", DER)])],
              "Alcance de los datos: 4 CEDIS, 120 productos, del 1 de septiembre de 2025 al 4 de noviembre de 2026.", 91),
    ]


def fila(*tarjetas):
    out = []
    for i, (n, m, t, a) in enumerate(tarjetas):
        x, w = cuarto(i)
        out.append(tarjeta(n, m, (x, TAR_Y, w, TAR_H), t, a, i + 1))
    return out


IZQ_W = 220                       # columna de segmentadores
DER_X = M + IZQ_W + G             # 248
DER_W = ANCHO - M - DER_X         # 1016

PAGINAS = [
    ("existencias", "Existencias", encabezado("existencias", "Existencias", "existencia diaria reconstruida desde el libro de movimientos") + fila(
        ("c_exist", "Existencia (u)", "Existencia al último día (u)", "Tarjeta con la existencia total en unidades al último día del periodo filtrado."),
        ("c_cero", "Productos en cero (último día)", "CEDIS-producto en cero al último día", "Tarjeta con cuántas combinaciones de CEDIS y producto están en cero el último día."),
        ("c_disp", "Disponibilidad", "Disponibilidad (días con existencia)", "Tarjeta con la parte de los días-producto que tuvo existencia."),
        ("c_perd", "Venta perdida estimada (u)", "Venta perdida estimada (u)", "Tarjeta con las unidades que se dejaron de vender por estar en cero, sin control de sustitución."),
    ) + [
        visual("s_cedis", "slicer", (M, CUERPO_Y, IZQ_W, 168), {"Values": proj(col("dim_almacen", "nombre", "CEDIS"), activo=True)}, "CEDIS", "Segmentador por CEDIS.", 5),
        visual("s_cat", "slicer", (M, CUERPO_Y + 168 + G, IZQ_W, 196), {"Values": proj(col("dim_producto", "categoria"), activo=True)}, "Categoría", "Segmentador por categoría de producto.", 6),
        visual("s_mes", "slicer", (M, CUERPO_Y + 168 + 196 + 2 * G, IZQ_W, FONDO_Y - (CUERPO_Y + 168 + 196 + 2 * G)),
               {"Values": proj(col("dim_fecha", "anio_mes"), activo=True)}, "Mes", "Segmentador por mes.", 10),
        visual("l_exist", "lineChart", (DER_X, CUERPO_Y, DER_W, 262),
               {"Category": proj(col("dim_fecha", "fecha"), activo=True), "Y": proj(med("Existencia (u)"))},
               "Existencia diaria reconstruida (u)", "Gráfica de línea con la existencia diaria reconstruida, de septiembre 2025 a noviembre 2026.", 7),
        visual("b_disp", "clusteredBarChart", (DER_X, CUERPO_Y + 262 + G, 400, FONDO_Y - (CUERPO_Y + 262 + G)),
               {"Category": proj(col("dim_almacen", "nombre", "CEDIS"), activo=True), "Y": proj(med("Disponibilidad"))},
               "Disponibilidad por CEDIS", "Gráfica de barras con la disponibilidad de cada CEDIS.", 8),
        visual("t_cero", "tableEx", (DER_X + 400 + G, CUERPO_Y + 262 + G, DER_W - 400 - G, FONDO_Y - (CUERPO_Y + 262 + G)),
               {"Values": proj(col("dim_producto", "producto", "Producto"), col("dim_producto", "categoria", "Categoría"), med("Días en cero"), med("Venta perdida estimada (u)"))},
               "Productos con más días en cero", "Tabla de productos ordenada por días en cero, con la venta perdida estimada.", 9,
               orden=(med("Días en cero"), "Descending")),
    ]),
    ("movimientos", "Movimientos", encabezado("movimientos", "Movimientos", "entradas, salidas y ajustes del libro de movimientos") + fila(
        ("c_ent", "Entradas (u)", "Entradas (u)", "Tarjeta con las unidades que entraron a los CEDIS."),
        ("c_sal", "Salidas (u)", "Salidas (u)", "Tarjeta con las unidades que salieron de los CEDIS."),
        ("c_lin", "Líneas de movimiento", "Registros en el libro", "Tarjeta con el número de registros del libro de movimientos."),
        ("c_aju", "Ajustes netos (u)", "Ajustes netos por merma y conteo (u)", "Tarjeta con las unidades netas de ajustes por merma y por conteo."),
    ) + [
        visual("k_mes", "clusteredColumnChart", (M, CUERPO_Y, 820, 300),
               {"Category": proj(col("dim_fecha", "anio_mes"), activo=True), "Y": proj(med("Entradas (u)"), med("Salidas (u)"))},
               "Entradas y salidas por mes (u) · noviembre 2026 llega al día 4", "Gráfica de columnas con entradas y salidas de unidades por mes.", 5),
        visual("b_tipo", "clusteredBarChart", (M + 820 + G, CUERPO_Y, UTIL - 820 - G, 300),
               {"Category": proj(col("fct_movimiento", "tipo"), activo=True), "Y": proj(med("Líneas de movimiento"))},
               "Registros por tipo de movimiento", "Gráfica de barras con el número de registros por tipo de movimiento.", 6,
               orden=(med("Líneas de movimiento"), "Descending")),
        visual("t_cedis", "tableEx", (M, CUERPO_Y + 300 + G, 820, FONDO_Y - (CUERPO_Y + 300 + G)),
               {"Values": proj(col("dim_almacen", "nombre", "CEDIS"), med("Entradas (u)"), med("Salidas (u)"), med("Ajustes netos (u)"),
                               med("Existencia (u)"), med("Venta diaria 30 d (u)"), med("Días de cobertura"), med("Disponibilidad"))},
               "Resumen por CEDIS", "Tabla por CEDIS con entradas, salidas, ajustes, existencia, venta diaria, días de cobertura y disponibilidad.", 7),
        visual("b_cob", "clusteredBarChart", (M + 820 + G, CUERPO_Y + 300 + G, UTIL - 820 - G, FONDO_Y - (CUERPO_Y + 300 + G)),
               {"Category": proj(col("dim_almacen", "nombre", "CEDIS"), activo=True), "Y": proj(med("Días de cobertura"))},
               "Días de cobertura al último día", "Gráfica de barras con los días que alcanza la existencia de cada CEDIS a la venta de los últimos 30 días.", 8,
               orden=(med("Días de cobertura"), "Descending")),
    ]),
    ("validacion", "Validación", encabezado("validacion", "Validación", "la reconstrucción contra un conteo físico hecho por otra vía") + fila(
        ("c_par", "Pares validados", "Pares CEDIS-producto contados", "Tarjeta con cuántas combinaciones de CEDIS y producto tienen conteo físico."),
        ("c_exa", "Coincidencia exacta", "Coincidencia exacta con el conteo", "Tarjeta con la parte de los pares donde la existencia reconstruida es igual al conteo físico."),
        ("c_cer", "Acierto en cero", "Acierto al decir si estaba en cero", "Tarjeta con la parte de los pares donde la reconstrucción y el conteo coinciden en si había o no existencia."),
        ("c_err", "Error medio (u)", "Error medio (u)", "Tarjeta con la diferencia absoluta promedio entre reconstrucción y conteo."),
    ) + [
        visual("x_val", "scatterChart", (M, CUERPO_Y, 500, FONDO_Y - CUERPO_Y),
               {"Category": proj(col("dim_producto", "sku"), activo=True), "X": proj(med("Conteo físico (u)")), "Y": proj(med("Reconstruido (u)"))},
               "Conteo físico (X) contra existencia reconstruida (Y)", "Gráfica de dispersión: cada punto es un producto; sobre la diagonal la reconstrucción coincide con el conteo.", 5),
        visual("b_val", "clusteredBarChart", (M + 500 + G, CUERPO_Y, UTIL - 500 - G, 250),
               {"Category": proj(col("dim_almacen", "nombre", "CEDIS"), activo=True), "Y": proj(med("Coincidencia exacta"), med("Acierto en cero"))},
               "Calidad de la reconstrucción por CEDIS", "Gráfica de barras con coincidencia exacta y acierto en cero por CEDIS.", 6),
        visual("t_dif", "tableEx", (M + 500 + G, CUERPO_Y + 250 + G, UTIL - 500 - G, FONDO_Y - (CUERPO_Y + 250 + G)),
               {"Values": proj(col("dim_almacen", "nombre", "CEDIS"), col("dim_producto", "producto", "Producto"), med("Conteo físico (u)"), med("Reconstruido (u)"), med("Error medio (u)"))},
               "Productos con mayor diferencia", "Tabla de productos ordenada por la diferencia entre conteo y reconstrucción.", 7,
               orden=(med("Error medio (u)"), "Descending")),
    ]),
]


def construir_reporte(base):
    d = os.path.join(base, "definition")
    jdump(os.path.join(base, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": tag("logical", "report")}})
    jdump(os.path.join(base, "definition.pbir"), {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}}})
    jdump(os.path.join(d, "version.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"})
    jdump(os.path.join(base, "StaticResources", "RegisteredResources", NOMBRE_TEMA), TEMA)
    version_import = {"visual": "1.8.91", "report": "2.0.91", "page": "1.3.91"}
    jdump(os.path.join(d, "report.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU06", "reportVersionAtImport": version_import, "type": "SharedResources"},
            "customTheme": {"name": NOMBRE_TEMA, "reportVersionAtImport": version_import, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": NOMBRE_TEMA, "path": NOMBRE_TEMA, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
    jdump(os.path.join(d, "pages", "pages.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p[0] for p in PAGINAS], "activePageName": PAGINAS[0][0]})
    for nombre, titulo, visuales in PAGINAS:
        jdump(os.path.join(d, "pages", nombre, "page.json"),
              {"$schema": PG, "name": nombre, "displayName": titulo, "displayOption": "FitToPage", "height": 720, "width": 1280})
        for v in visuales:
            jdump(os.path.join(d, "pages", nombre, "visuals", v["name"], "visual.json"), v)


def main():
    for sub in (f"{NOMBRE}.Report", f"{NOMBRE}.SemanticModel"):
        p = os.path.join(RAIZ, sub)
        if os.path.isdir(p):
            # se borran los archivos generados; las carpetas vacías se toleran porque
            # OneDrive puede retenerlas un momento mientras sincroniza
            for raiz, _, archivos in os.walk(p, topdown=False):
                if any(x in raiz.split(os.sep) for x in (".pbi", "cultures")):
                    continue  # caché, ajustes del editor y esquema de idioma de Power BI
                for a in archivos:
                    if a == "diagramLayout.json":
                        continue
                    os.remove(os.path.join(raiz, a))
                try:
                    os.rmdir(raiz)
                except OSError:
                    pass
    construir_modelo(os.path.join(RAIZ, f"{NOMBRE}.SemanticModel"))
    construir_reporte(os.path.join(RAIZ, f"{NOMBRE}.Report"))
    jdump(os.path.join(RAIZ, f"{NOMBRE}.pbip"),
          {"version": "1.0", "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}], "settings": {}})
    escribir(os.path.join(RAIZ, ".gitignore"), "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n__pycache__/\n")
    print(f"PBIP escrito en {RAIZ} (origen: {FUENTE})")


if __name__ == "__main__":
    main()
