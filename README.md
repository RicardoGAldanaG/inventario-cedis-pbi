# Inventario CEDIS · existencia diaria reconstruida

Demo de portafolio en PostgreSQL y Power BI del **Caso 1** del
[portafolio de Ricardo Aldana](https://linkedin.com/in/ricardo-aldana-data-analyst-bi): el ERP solo
guarda la existencia de hoy y el libro de movimientos; la existencia de cada día se reconstruye
hacia atrás y se valida contra un conteo físico hecho por otra vía.

| Medida | Resultado en el demo |
|---|---|
| Coincidencia exacta con el conteo físico | 83.1% de 480 pares CEDIS-producto |
| Acierto al decir si estaba en cero | 99.0% |
| Error medio | 0.33 unidades |
| Disponibilidad | 97.0% de los días-producto |

**Los datos son sintéticos**: 4 CEDIS, 120 productos, del 1-sep-2025 al 4-nov-2026, generados
con semilla fija para que el ejemplo sea reproducible.

## Flujo

```
datos/*.csv ──► PostgreSQL: inventario.*  ──► vistas pbi.*  ──► Power BI (InventarioCEDIS.pbip)
 (exportación     libro, saldo y conteo        una por tabla      3 páginas, 18 medidas DAX
  del ERP)        + reconstrucción en SQL       del modelo
```

La reconstrucción se hace dos veces, en SQL y en Python, y el resultado es idéntico fila por fila
(`sql/06_comparar_python.sql`).

## SQL (PostgreSQL 12+)

| Archivo | Qué hace |
|---|---|
| `01_esquema.sql` | Tablas de origen con llaves y restricciones de negocio (el signo de cada movimiento corresponde a su tipo) |
| `02_carga.sql` | Carga los CSV con `\copy` y rechaza movimientos fuera del periodo |
| `03_reconstruccion.sql` | Rejilla par × día, existencia con `SUM() OVER (ORDER BY fecha DESC)`, validación con LEFT JOIN y rachas de días en cero (huecos e islas) |
| `04_vistas_pbi.sql` | Capa de consumo `pbi.*` con las mismas columnas que el modelo |
| `05_pruebas.sql` | 6 pruebas de integridad: último día = saldo, rejilla completa, cambio diario = neto del libro, sin negativos, universo del conteo, rachas = días en cero |
| `06_comparar_python.sql` | Comparación fila por fila contra la salida de Python |

```powershell
.\sql\pg_local.ps1 crear      # una vez: clúster local en el puerto 5433, solo localhost
.\sql\pg_local.ps1 iniciar
.\sql\construir.ps1           # esquema, carga, reconstrucción y pruebas (unos segundos)
```

`pg_local.ps1` usa los binarios de PostgreSQL 12 sin servicio de Windows ni permisos de
administrador. La autenticación es `trust` limitada a 127.0.0.1: sirve para un demo local, no para
un servidor compartido. Para usar otro servidor: `.\sql\construir.ps1 -Puerto 5432 -Usuario postgres`.

## Abrir el reporte

**Con PostgreSQL** (origen por defecto):
1. Construye la base con los pasos de arriba.
2. Doble clic en `InventarioCEDIS.pbip`. Los parámetros `Servidor` (`localhost:5433`) y `BaseDatos`
   (`inventario_cedis`) están en **Transformar datos → Administrar parámetros**.
3. **Actualizar**. La primera vez, en **Base de datos**, usuario `postgres` y cualquier contraseña
   (el clúster local no la revisa); acepta conectar sin cifrado.

**Sin PostgreSQL**: `python scripts/construir_pbip.py --csv` cambia el origen a los archivos de
`datos/`, con la ruta de tu copia en el parámetro `RutaDatos`.

## Páginas

| Página | Qué responde |
|---|---|
| Existencias | Existencia diaria reconstruida, disponibilidad por CEDIS, productos con más días en cero y venta perdida estimada |
| Movimientos | Entradas y salidas por mes, registros por tipo, resumen por CEDIS con días de cobertura |
| Validación | Qué tan bien coincide la reconstrucción con el conteo físico: exacta, en cero y error medio |

## Cómo se construye

```
python scripts/generar_datos.py           # libro de movimientos, saldo de hoy y conteo físico
python scripts/reconstruir_existencias.py # existencia diaria + validación (versión Python)
.\sql\construir.ps1                       # la misma reconstrucción en PostgreSQL
python scripts/construir_pbip.py          # modelo TMDL y reporte PBIR (--csv para origen de archivos)
```

Los scripts de Python solo usan la librería estándar. `construir_pbip.py` reescribe el modelo y el
reporte (conserva la caché y los ajustes que Power BI guarda): los cambios hechos a mano en Power BI
Desktop se pierden si se vuelve a correr.

## Reglas del método

- `existencia(d) = saldo_hoy − suma(movimientos posteriores a d)`.
- La validación parte del universo del conteo (LEFT JOIN): nulo no es cero.
- Entradas y Salidas se cuentan por tipo de movimiento; mermas, ajustes y traspasos van aparte.
- La venta perdida estimada multiplica los días en cero por la venta diaria que el producto tiene
  cuando sí hay existencia. No controla sustitución, así que es un techo, no una cifra para sumar.
