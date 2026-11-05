"""Genera el libro de movimientos sintético de 4 CEDIS y el conteo físico de validación.

Simula la operación real día por día:
  - salidas por demanda (Poisson) limitadas por la existencia física,
  - reabasto por punto de reorden con tiempo de entrega y retrasos ocasionales,
  - traspasos entre CEDIS y ajustes por merma,
  - merma física NO registrada en el sistema (la causa de que el conteo no cuadre).

Escribe en ../datos/:
  dim_almacen.csv, dim_producto.csv, dim_fecha.csv,
  fct_movimiento.csv      (el libro de movimientos que exporta el ERP)
  saldo_hoy.csv           (existencia del sistema al cierre del último día)
  conteo_fisico.csv       (conteo independiente en una fecha de corte)

Solo usa la librería estándar. Semilla fija: los datos son reproducibles.
"""
import csv
import math
import os
import random
from datetime import date, timedelta

SEMILLA = 20261105
INICIO = date(2025, 9, 1)
FIN = date(2026, 11, 4)          # último día con movimientos
CORTE_CONTEO = date(2026, 10, 23)  # fecha del conteo físico independiente
N_PRODUCTOS = 120

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.normpath(os.path.join(AQUI, "..", "datos"))

ALMACENES = [
    ("TLA", "Tlalnepantla", "Estado de México", 1.00),
    ("IZT", "Iztapalapa", "Ciudad de México", 1.35),
    ("QRO", "Querétaro", "Querétaro", 0.70),
    ("GDL", "Guadalajara", "Jalisco", 0.85),
]
CATEGORIAS = [
    # categoría, cliente, demanda diaria base (min, max), días de entrega (min, max)
    ("Abarrotes", "Cliente F", (2.0, 9.0), (3, 6)),
    ("Bebidas", "Cliente B", (3.0, 12.0), (2, 5)),
    ("Farmacia", "Cliente A", (0.8, 4.0), (4, 8)),
    ("Electrónica", "Cliente C", (0.4, 2.5), (6, 12)),
    ("Hogar", "Cliente E", (0.5, 3.0), (5, 10)),
    ("Autopartes", "Cliente D", (0.3, 1.8), (7, 14)),
]
NOMBRES = {
    "Abarrotes": ["Arroz 1 kg", "Frijol 900 g", "Aceite 1 L", "Azúcar 2 kg", "Pasta 200 g", "Atún 140 g", "Café 400 g", "Avena 800 g"],
    "Bebidas": ["Agua 1.5 L", "Refresco 600 ml", "Jugo 1 L", "Bebida isotónica 1 L", "Agua mineral 2 L", "Té frío 600 ml"],
    "Farmacia": ["Paracetamol 500 mg", "Ibuprofeno 400 mg", "Suero oral 625 ml", "Gel antibacterial 1 L", "Vendas 10 cm", "Vitamina C 1 g"],
    "Electrónica": ["Audífonos inalámbricos", "Cargador 33 W", "Batería portátil 10000 mAh", "Cable USB-C 1 m", "Bocina Bluetooth", "Reloj inteligente"],
    "Hogar": ["Detergente 5 kg", "Suavizante 3 L", "Papel higiénico 12 pz", "Bolsas basura 30 pz", "Limpiador multiusos 1 L", "Esponjas 3 pz"],
    "Autopartes": ["Filtro de aceite", "Balatas delanteras", "Bujía iridio", "Anticongelante 4 L", "Aceite 5W-30 4 L", "Escobilla 22 in"],
}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
# temporada: el pico de noviembre y diciembre, el valle de enero y febrero
TEMPORADA = {1: .85, 2: .88, 3: .95, 4: .97, 5: 1.04, 6: .98, 7: .96, 8: .98, 9: 1.0, 10: 1.03, 11: 1.22, 12: 1.30}
SEMANA = [1.05, 1.0, 1.0, 1.02, 1.12, .95, .55]


def poisson(rnd, lam):
    if lam <= 0:
        return 0
    if lam > 30:  # aproximación normal para tasas altas
        return max(0, int(round(rnd.gauss(lam, math.sqrt(lam)))))
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= l:
            return k
        k += 1


def escribir(nombre, encabezado, filas):
    ruta = os.path.join(SALIDA, nombre)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(encabezado)
        w.writerows(filas)
    return ruta


def main():
    rnd = random.Random(SEMILLA)
    os.makedirs(SALIDA, exist_ok=True)

    # --- catálogo ---
    productos = []
    for i in range(N_PRODUCTOS):
        cat, cliente, (dmin, dmax), entrega = CATEGORIAS[i % len(CATEGORIAS)]
        nombre = NOMBRES[cat][(i // len(CATEGORIAS)) % len(NOMBRES[cat])]
        variante = i // (len(CATEGORIAS) * len(NOMBRES[cat]))
        productos.append({
            "sku": f"SKU-{1001 + i}",
            "producto": nombre + (f" · lote {variante + 1}" if variante else ""),
            "categoria": cat,
            "cliente": cliente,
            "demanda": rnd.uniform(dmin, dmax),
            "entrega": entrega,
        })

    dias = [INICIO + timedelta(d) for d in range((FIN - INICIO).days + 1)]
    movimientos = []      # lo que registra el sistema
    saldo_sistema = {}    # existencia según el sistema al cierre de FIN
    fisico_al_corte = {}  # existencia física real el día del conteo
    sistema_al_corte = {}

    for alm, _, _, escala in ALMACENES:
        for p in productos:
            lam0 = p["demanda"] * escala * rnd.uniform(.6, 1.4)
            emin, emax = p["entrega"]
            punto_reorden = lam0 * emax * 1.3
            lote = max(6, round(lam0 * rnd.uniform(18, 35)))
            fisico = round(lote * rnd.uniform(.6, 1.2))
            sistema = fisico
            pedidos = []  # (fecha de llegada, cantidad)
            for d in dias:
                # 1) llegan pedidos
                llega = sum(q for f, q in pedidos if f == d)
                pedidos = [(f, q) for f, q in pedidos if f != d]
                if llega:
                    fisico += llega
                    sistema += llega
                    movimientos.append((d, alm, p["sku"], "Entrada", llega))
                # 2) salidas por demanda
                lam = lam0 * TEMPORADA[d.month] * SEMANA[d.weekday()]
                pedido = poisson(rnd, lam)
                sale = min(pedido, max(fisico, 0), max(sistema, 0))
                if sale:
                    fisico -= sale
                    sistema -= sale
                    movimientos.append((d, alm, p["sku"], "Salida", -sale))
                # 3) traspasos ocasionales a otro CEDIS (registrados)
                if sistema > lote * 1.5 and rnd.random() < .01:
                    q = round(lote * .3)
                    fisico -= q
                    sistema -= q
                    movimientos.append((d, alm, p["sku"], "Traspaso salida", -q))
                # 4) merma: a veces se registra el ajuste, a veces no
                if fisico > 0 and rnd.random() < .004:
                    q = min(fisico, rnd.randint(1, 3))
                    fisico -= q
                    if rnd.random() < .45:  # el ajuste sí se captura
                        sistema -= q
                        movimientos.append((d, alm, p["sku"], "Ajuste merma", -q))
                # el conteo cíclico corrige el sistema cada ~90 días por producto
                if rnd.random() < 1 / 90 and sistema != fisico:
                    movimientos.append((d, alm, p["sku"], "Ajuste conteo", fisico - sistema))
                    sistema = fisico
                # 5) reorden: si lo disponible + en camino cae del punto de reorden
                en_camino = sum(q for _, q in pedidos)
                if sistema + en_camino <= punto_reorden:
                    espera = rnd.randint(emin, emax)
                    if rnd.random() < .12:  # retraso del proveedor
                        espera += rnd.randint(5, 18)
                    pedidos.append((d + timedelta(espera), lote))
                if d == CORTE_CONTEO:
                    fisico_al_corte[(alm, p["sku"])] = fisico
                    sistema_al_corte[(alm, p["sku"])] = sistema
            saldo_sistema[(alm, p["sku"])] = sistema

    # --- conteo físico independiente: la existencia física, con error de captura ---
    conteo = []
    for (alm, sku), real in sorted(fisico_al_corte.items()):
        contado = real
        if rnd.random() < .03:  # error de conteo
            contado = max(0, real + rnd.choice([-2, -1, 1, 2]))
        conteo.append((CORTE_CONTEO.isoformat(), alm, sku, contado))

    # --- escribir ---
    escribir("dim_almacen.csv", ["almacen", "nombre", "estado"],
             [(a, n, e) for a, n, e, _ in ALMACENES])
    escribir("dim_producto.csv", ["sku", "producto", "categoria", "cliente"],
             [(p["sku"], p["producto"], p["categoria"], p["cliente"]) for p in productos])
    escribir("dim_fecha.csv",
             ["fecha", "anio", "mes", "anio_mes", "nombre_mes", "dia_semana", "nombre_dia", "es_fin_de_semana"],
             [(d.isoformat(), d.year, d.month, f"{d.year}-{d.month:02d}", MESES[d.month - 1],
               d.isoweekday(), DIAS[d.weekday()], "true" if d.weekday() >= 5 else "false") for d in dias])
    movimientos.sort(key=lambda m: (m[0], m[1], m[2]))
    escribir("fct_movimiento.csv", ["fecha", "almacen", "sku", "tipo", "cantidad"],
             [(d.isoformat(), a, s, t, q) for d, a, s, t, q in movimientos])
    escribir("saldo_hoy.csv", ["almacen", "sku", "existencia"],
             [(a, s, q) for (a, s), q in sorted(saldo_sistema.items())])
    escribir("conteo_fisico.csv", ["fecha", "almacen", "sku", "conteo"], conteo)

    print(f"productos={len(productos)} almacenes={len(ALMACENES)} dias={len(dias)} "
          f"movimientos={len(movimientos):,} carpeta={SALIDA}")


if __name__ == "__main__":
    main()
