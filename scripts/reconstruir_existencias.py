"""Reconstruye la existencia diaria por CEDIS y producto a partir del libro de movimientos.

El ERP guarda la existencia de HOY y los movimientos (flujos), no la existencia de cada día.
El nivel al cierre de un día se obtiene partiendo del saldo de hoy y deshaciendo, hacia atrás,
todos los movimientos posteriores a ese día:

    existencia(d) = saldo_hoy - suma(movimientos con fecha > d)

Después se valida contra un conteo físico hecho por otra vía. La validación usa el universo
del conteo como base (equivale a un LEFT JOIN): un producto sin movimientos sigue contando,
porque nulo no es cero y un INNER JOIN tiraría justo los ceros que se quieren medir.

Lee de ../datos/:  dim_fecha.csv, fct_movimiento.csv, saldo_hoy.csv, conteo_fisico.csv
Escribe en ../datos/:
  fct_existencia_diaria.csv  fecha, almacen, sku, existencia, en_cero, venta_perdida_est
  fct_validacion.csv         almacen, sku, conteo, reconstruido, diferencia, coincide_exacto, coincide_cero

Solo usa la librería estándar.
"""
import csv
import os
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.normpath(os.path.join(AQUI, "..", "datos"))


def leer(nombre):
    with open(os.path.join(DATOS, nombre), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    fechas = [r["fecha"] for r in leer("dim_fecha.csv")]          # ordenadas, ISO
    saldo = {(r["almacen"], r["sku"]): int(r["existencia"]) for r in leer("saldo_hoy.csv")}

    # movimiento neto por (almacén, sku, fecha) y salidas por demanda
    neto = defaultdict(int)
    salidas = defaultdict(int)
    for m in leer("fct_movimiento.csv"):
        k = (m["almacen"], m["sku"])
        q = int(m["cantidad"])
        neto[(k, m["fecha"])] += q
        if m["tipo"] == "Salida":
            salidas[k] += -q

    filas = []
    nivel_en = {}  # (almacén, sku, fecha) -> existencia reconstruida
    for k, hoy in sorted(saldo.items()):
        # recorrer hacia atrás: el nivel del día d es el del día d+1 menos el neto del día d+1
        serie = {}
        nivel = hoy
        for i in range(len(fechas) - 1, -1, -1):
            d = fechas[i]
            serie[d] = nivel
            nivel -= neto.get((k, d), 0)   # deshace los movimientos de ese día
        dias_con = sum(1 for d in fechas if serie[d] > 0)
        tasa = salidas[k] / dias_con if dias_con else 0.0  # venta diaria cuando sí hay existencia
        for d in fechas:
            e = serie[d]
            cero = e <= 0
            filas.append((d, k[0], k[1], e, "true" if cero else "false", round(tasa, 3) if cero else 0))
            nivel_en[(k[0], k[1], d)] = e

    with open(os.path.join(DATOS, "fct_existencia_diaria.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "almacen", "sku", "existencia", "en_cero", "venta_perdida_est"])
        w.writerows(filas)

    # validación contra el conteo físico (el conteo es el universo: LEFT JOIN)
    val = []
    for c in leer("conteo_fisico.csv"):
        rec = nivel_en.get((c["almacen"], c["sku"], c["fecha"]))
        conteo = int(c["conteo"])
        rec = 0 if rec is None else rec
        dif = rec - conteo
        val.append((c["almacen"], c["sku"], conteo, rec, dif,
                    "true" if dif == 0 else "false",
                    "true" if (rec <= 0) == (conteo <= 0) else "false"))
    with open(os.path.join(DATOS, "fct_validacion.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["almacen", "sku", "conteo", "reconstruido", "diferencia", "coincide_exacto", "coincide_cero"])
        w.writerows(val)

    n = len(val)
    exacto = sum(1 for v in val if v[5] == "true") / n
    cero = sum(1 for v in val if v[6] == "true") / n
    error = sum(abs(v[4]) for v in val) / n
    en_cero = sum(1 for r in filas if r[4] == "true") / len(filas)
    print(f"filas existencia={len(filas):,}  pares validados={n}  exacto={exacto:.1%}  "
          f"acierto en cero={cero:.1%}  error medio={error:.2f} u  días-producto en cero={en_cero:.1%}")


if __name__ == "__main__":
    main()
