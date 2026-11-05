-- Consultas de práctica sobre la base del demo (PostgreSQL, localhost:5433, base inventario_cedis).
-- Selecciona una consulta y ejecútala sola: en VS Code, con el botón de ejecutar (▷) de la esquina
-- superior derecha del editor o con Ctrl+Shift+E. Sin selección se ejecuta todo el archivo.
-- Van de lo básico a funciones de ventana; cada una responde una pregunta de operación de CEDIS.


-- 1. ¿Qué hay en la base?
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema IN ('inventario', 'pbi')
ORDER BY 1, 2;


-- 2. Movimientos por tipo: cuántos registros y cuántas unidades
SELECT tipo, COUNT(*) AS registros, SUM(cantidad) AS unidades
FROM inventario.movimiento
GROUP BY tipo
ORDER BY registros DESC;


-- 3. Entradas y salidas por CEDIS y mes
SELECT a.nombre AS cedis,
       to_char(m.fecha, 'YYYY-MM') AS mes,
       SUM(m.cantidad) FILTER (WHERE m.tipo = 'Entrada') AS entradas,
       -SUM(m.cantidad) FILTER (WHERE m.tipo = 'Salida')  AS salidas
FROM inventario.movimiento m
JOIN inventario.almacen a USING (almacen)
GROUP BY a.nombre, mes
ORDER BY cedis, mes;


-- 4. Disponibilidad por CEDIS: parte de los días-producto con existencia
SELECT a.nombre AS cedis,
       COUNT(*) AS dias_producto,
       COUNT(*) FILTER (WHERE e.en_cero) AS dias_en_cero,
       ROUND(100.0 * COUNT(*) FILTER (WHERE NOT e.en_cero) / COUNT(*), 1) AS disponibilidad_pct
FROM inventario.existencia_diaria e
JOIN inventario.almacen a USING (almacen)
GROUP BY a.nombre
ORDER BY disponibilidad_pct;


-- 5. Los 10 productos con más días en cero y su venta perdida estimada
SELECT p.producto, p.categoria, e.almacen,
       COUNT(*) FILTER (WHERE e.en_cero) AS dias_en_cero,
       ROUND(SUM(e.venta_perdida_est), 0) AS venta_perdida_u
FROM inventario.existencia_diaria e
JOIN inventario.producto p USING (sku)
GROUP BY p.producto, p.categoria, e.almacen
ORDER BY dias_en_cero DESC
LIMIT 10;


-- 6. Rachas de desabasto más largas (huecos e islas, vista inventario.rachas_cero)
SELECT r.almacen, p.producto, r.desde, r.hasta, r.dias
FROM inventario.rachas_cero r
JOIN inventario.producto p USING (sku)
ORDER BY r.dias DESC
LIMIT 10;


-- 7. Existencia de un producto día por día, con el movimiento neto del día
--    (cambia el sku y el almacén para ver otro)
SELECT e.fecha, e.existencia,
       COALESCE(SUM(m.cantidad), 0) AS neto_del_dia
FROM inventario.existencia_diaria e
LEFT JOIN inventario.movimiento m USING (almacen, sku, fecha)
WHERE e.sku = 'SKU-1001' AND e.almacen = 'TLA'
GROUP BY e.fecha, e.existencia
ORDER BY e.fecha
LIMIT 60;


-- 8. Días de cobertura al último día: existencia ÷ venta diaria de los últimos 30 días
WITH ultimo AS (SELECT fin FROM inventario.periodo),
venta AS (
    SELECT almacen, sku, -SUM(cantidad) / 30.0 AS venta_dia
    FROM inventario.movimiento, ultimo
    WHERE tipo = 'Salida' AND fecha > ultimo.fin - 30
    GROUP BY almacen, sku
)
SELECT e.almacen, p.producto, e.existencia,
       ROUND(v.venta_dia, 2) AS venta_dia,
       ROUND(e.existencia / NULLIF(v.venta_dia, 0), 1) AS dias_cobertura
FROM inventario.existencia_diaria e
JOIN ultimo ON e.fecha = ultimo.fin
JOIN inventario.producto p USING (sku)
LEFT JOIN venta v USING (almacen, sku)
ORDER BY dias_cobertura NULLS LAST
LIMIT 15;


-- 9. Ranking de productos por salidas dentro de cada categoría (función de ventana)
SELECT *
FROM (
    SELECT p.categoria, p.producto,
           -SUM(m.cantidad) AS salidas,
           RANK() OVER (PARTITION BY p.categoria ORDER BY -SUM(m.cantidad) DESC) AS lugar
    FROM inventario.movimiento m
    JOIN inventario.producto p USING (sku)
    WHERE m.tipo = 'Salida'
    GROUP BY p.categoria, p.producto
) t
WHERE lugar <= 3
ORDER BY categoria, lugar;


-- 10. Validación: dónde no cuadra la reconstrucción con el conteo físico
SELECT v.almacen, p.producto, v.conteo, v.reconstruido, v.diferencia
FROM inventario.validacion v
JOIN inventario.producto p USING (sku)
WHERE NOT v.coincide_exacto
ORDER BY ABS(v.diferencia) DESC;


-- 11. Tu turno: ¿qué cliente concentra más días en cero? (pista: producto.cliente)
