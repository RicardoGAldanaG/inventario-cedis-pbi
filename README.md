# Inventario CEDIS · existencia diaria reconstruida

Demo de portafolio en Power BI del **Caso 1** del
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

## Abrir

1. Clona el repo o descárgalo como ZIP.
2. Doble clic en `InventarioCEDIS.pbip` (Power BI Desktop, formato de proyecto PBIP).
3. En **Transformar datos → Administrar parámetros → RutaDatos** escribe la ruta de la carpeta
   `datos` de tu copia, terminada en `\` (por ejemplo `C:\repos\inventario-cedis-pbi\datos\`).
4. **Inicio → Actualizar**.

Otra opción: correr `python scripts/construir_pbip.py` en tu copia, que escribe la ruta correcta solo.

## Páginas

| Página | Qué responde |
|---|---|
| Existencias | Existencia diaria reconstruida, disponibilidad por CEDIS, productos con más días en cero y venta perdida estimada |
| Movimientos | Entradas y salidas por mes, registros por tipo, resumen por CEDIS con días de cobertura |
| Validación | Qué tan bien coincide la reconstrucción con el conteo físico: exacta, en cero y error medio |

## Cómo se construye

```
python scripts/generar_datos.py           # libro de movimientos, saldo de hoy y conteo físico
python scripts/reconstruir_existencias.py # existencia diaria + validación
python scripts/construir_pbip.py          # modelo TMDL y reporte PBIR
```

Solo usan la librería estándar de Python. `construir_pbip.py` reescribe el reporte: los cambios
hechos a mano en Power BI Desktop se pierden si se vuelve a correr.

## Reglas del método

- `existencia(d) = saldo_hoy − suma(movimientos posteriores a d)`.
- La validación parte del universo del conteo (LEFT JOIN): nulo no es cero.
- La venta perdida estimada multiplica los días en cero por la venta diaria que el producto tiene
  cuando sí hay existencia. No controla sustitución, así que es un techo, no una cifra para sumar.
