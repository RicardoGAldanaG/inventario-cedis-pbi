"""Escribe el proyecto de Power BI (PBIP: modelo en TMDL + reporte en PBIR) sobre ../datos/.

Se vuelve a correr cuando cambian las medidas o las páginas. La ruta de los CSV queda en el
parámetro RutaDatos del modelo (Transformar datos > Parámetros) por si la carpeta se mueve.
"""
import json
import os
import shutil
import uuid

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
DATOS = os.path.join(RAIZ, "datos") + os.sep
NOMBRE = "InventarioCEDIS"
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
    ("Disponibilidad", "1 - DIVIDE ( [Días en cero], [Días-producto] )", "0.0%", "Existencias"),
    ("Productos en cero (último día)", "CALCULATE ( [Días en cero], LASTDATE ( dim_fecha[fecha] ) )", "#,0", "Existencias"),
    ("Venta perdida estimada (u)", "SUM ( fct_existencia_diaria[venta_perdida_est] )", "#,0", "Existencias"),
    ("Entradas (u)", "CALCULATE ( SUM ( fct_movimiento[cantidad] ), fct_movimiento[cantidad] > 0 )", "#,0", "Movimientos"),
    ("Salidas (u)", "- CALCULATE ( SUM ( fct_movimiento[cantidad] ), fct_movimiento[cantidad] < 0 )", "#,0", "Movimientos"),
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
    out += [f"\tpartition {nombre} = m", "\t\tmode: import", "\t\tsource =",
            "\t\t\t\tlet",
            f'\t\t\t\t    Origen = Csv.Document(File.Contents(RutaDatos & "{t["csv"]}"), [Delimiter = ",", Columns = {len(t["cols"])}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
            "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),",
            f'\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos}}}, "en-US")',
            "\t\t\t\tin", "\t\t\t\t    Tipos", ""]
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
    orden = list(TABLAS) + ["RutaDatos"]
    modelo = ["model Model", "\tculture: es-MX", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
              "\tsourceQueryCulture: es-MX", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
              "annotation PBI_QueryOrder = " + json.dumps(orden, ensure_ascii=False), "",
              "annotation __PBI_TimeIntelligenceEnabled = 0", "",
              'annotation PBI_ProTooling = ["DevMode"]', ""]
    modelo += [f"ref table {t}" for t in list(TABLAS) + ["_Medidas"]]
    escribir(os.path.join(d, "model.tmdl"), "\n".join(modelo) + "\n\n")
    # en M la diagonal invertida no escapa nada: la ruta de Windows va tal cual
    escribir(os.path.join(d, "expressions.tmdl"),
             f'expression RutaDatos = "{DATOS}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
             f"\tlineageTag: {tag('e', 'RutaDatos')}\n\n"
             "\tannotation PBI_ResultType = Text\n\n")
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


def col(ent, prop):
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}},
            "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}


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


PAGINAS = [
    ("existencias", "Existencias", [
        tarjeta("c_exist", "Existencia (u)", (20, 20, 300, 100), "Existencia al último día", "Tarjeta con la existencia total en unidades al último día del periodo filtrado.", 1),
        tarjeta("c_cero", "Productos en cero (último día)", (330, 20, 300, 100), "Productos en cero hoy", "Tarjeta con cuántas combinaciones de CEDIS y producto están en cero el último día.", 2),
        tarjeta("c_disp", "Disponibilidad", (640, 20, 300, 100), "Disponibilidad", "Tarjeta con la parte de los días-producto que tuvo existencia.", 3),
        tarjeta("c_perd", "Venta perdida estimada (u)", (950, 20, 310, 100), "Venta perdida estimada (u)", "Tarjeta con las unidades que se dejaron de vender por estar en cero, sin control de sustitución.", 4),
        visual("s_cedis", "slicer", (20, 135, 240, 180), {"Values": proj(col("dim_almacen", "nombre"), activo=True)}, "CEDIS", "Segmentador por CEDIS.", 5),
        visual("s_cat", "slicer", (20, 325, 240, 225), {"Values": proj(col("dim_producto", "categoria"), activo=True)}, "Categoría", "Segmentador por categoría de producto.", 6),
        visual("l_exist", "lineChart", (270, 135, 990, 270),
               {"Category": proj(col("dim_fecha", "fecha"), activo=True), "Y": proj(med("Existencia (u)"))},
               "Existencia diaria reconstruida desde el libro de movimientos", "Gráfica de línea con la existencia diaria reconstruida, de septiembre 2025 a noviembre 2026.", 7),
        visual("b_disp", "barChart", (270, 420, 480, 280),
               {"Category": proj(col("dim_almacen", "nombre"), activo=True), "Y": proj(med("Disponibilidad"))},
               "Disponibilidad por CEDIS", "Gráfica de barras con la disponibilidad de cada CEDIS.", 8),
        visual("t_cero", "tableEx", (760, 420, 500, 280),
               {"Values": proj(col("dim_producto", "producto"), col("dim_producto", "categoria"), med("Días en cero"), med("Venta perdida estimada (u)"))},
               "Productos con más días en cero", "Tabla de productos ordenada por días en cero, con la venta perdida estimada.", 9,
               orden=(med("Días en cero"), "Descending")),
        visual("s_mes", "slicer", (20, 560, 240, 140), {"Values": proj(col("dim_fecha", "anio_mes"), activo=True)}, "Mes", "Segmentador por mes.", 10),
    ]),
    ("movimientos", "Movimientos", [
        tarjeta("c_ent", "Entradas (u)", (20, 20, 300, 100), "Entradas (u)", "Tarjeta con las unidades que entraron a los CEDIS.", 1),
        tarjeta("c_sal", "Salidas (u)", (330, 20, 300, 100), "Salidas (u)", "Tarjeta con las unidades que salieron de los CEDIS.", 2),
        tarjeta("c_lin", "Líneas de movimiento", (640, 20, 300, 100), "Líneas de movimiento", "Tarjeta con el número de registros del libro de movimientos.", 3),
        tarjeta("c_aju", "Ajustes netos (u)", (950, 20, 310, 100), "Ajustes netos (u)", "Tarjeta con las unidades netas de ajustes por merma y por conteo.", 4),
        visual("k_mes", "clusteredColumnChart", (20, 135, 800, 300),
               {"Category": proj(col("dim_fecha", "anio_mes"), activo=True), "Y": proj(med("Entradas (u)"), med("Salidas (u)"))},
               "Entradas y salidas por mes", "Gráfica de columnas con entradas y salidas de unidades por mes.", 5),
        visual("b_tipo", "barChart", (830, 135, 430, 300),
               {"Category": proj(col("fct_movimiento", "tipo"), activo=True), "Y": proj(med("Líneas de movimiento"))},
               "Registros por tipo de movimiento", "Gráfica de barras con el número de registros por tipo de movimiento.", 6),
        visual("t_cedis", "tableEx", (20, 450, 1240, 250),
               {"Values": proj(col("dim_almacen", "nombre"), med("Entradas (u)"), med("Salidas (u)"), med("Ajustes netos (u)"),
                               med("Existencia (u)"), med("Venta diaria 30 d (u)"), med("Días de cobertura"), med("Disponibilidad"))},
               "Resumen por CEDIS", "Tabla por CEDIS con entradas, salidas, ajustes, existencia, venta diaria, días de cobertura y disponibilidad.", 7),
    ]),
    ("validacion", "Validación", [
        tarjeta("c_par", "Pares validados", (20, 20, 300, 100), "Pares CEDIS-producto contados", "Tarjeta con cuántas combinaciones de CEDIS y producto tienen conteo físico.", 1),
        tarjeta("c_exa", "Coincidencia exacta", (330, 20, 300, 100), "Coincidencia exacta", "Tarjeta con la parte de los pares donde la existencia reconstruida es igual al conteo físico.", 2),
        tarjeta("c_cer", "Acierto en cero", (640, 20, 300, 100), "Acierto al decir si estaba en cero", "Tarjeta con la parte de los pares donde la reconstrucción y el conteo coinciden en si había o no existencia.", 3),
        tarjeta("c_err", "Error medio (u)", (950, 20, 310, 100), "Error medio (u)", "Tarjeta con la diferencia absoluta promedio entre reconstrucción y conteo.", 4),
        visual("x_val", "scatterChart", (20, 135, 620, 565),
               {"Category": proj(col("dim_producto", "sku"), activo=True), "X": proj(med("Conteo físico (u)")), "Y": proj(med("Reconstruido (u)"))},
               "Conteo físico contra existencia reconstruida", "Gráfica de dispersión: cada punto es un producto; sobre la diagonal la reconstrucción coincide con el conteo.", 5),
        visual("b_val", "barChart", (650, 135, 610, 250),
               {"Category": proj(col("dim_almacen", "nombre"), activo=True), "Y": proj(med("Coincidencia exacta"), med("Acierto en cero"))},
               "Calidad de la reconstrucción por CEDIS", "Gráfica de barras con coincidencia exacta y acierto en cero por CEDIS.", 6),
        visual("t_dif", "tableEx", (650, 395, 610, 305),
               {"Values": proj(col("dim_almacen", "nombre"), col("dim_producto", "producto"), med("Conteo físico (u)"), med("Reconstruido (u)"), med("Error medio (u)"))},
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
    jdump(os.path.join(d, "report.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU06",
                                          "reportVersionAtImport": {"visual": "1.8.91", "report": "2.0.91", "page": "1.3.91"},
                                          "type": "SharedResources"}},
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
            # conservar la caché local de Power BI no aporta nada: se regenera al abrir
            shutil.rmtree(p)
    construir_modelo(os.path.join(RAIZ, f"{NOMBRE}.SemanticModel"))
    construir_reporte(os.path.join(RAIZ, f"{NOMBRE}.Report"))
    jdump(os.path.join(RAIZ, f"{NOMBRE}.pbip"),
          {"version": "1.0", "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}], "settings": {}})
    escribir(os.path.join(RAIZ, ".gitignore"), "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print("PBIP escrito en", RAIZ)


if __name__ == "__main__":
    main()
