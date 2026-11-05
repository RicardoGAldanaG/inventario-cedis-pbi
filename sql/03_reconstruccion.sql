-- Existencia diaria reconstruida desde el libro de movimientos.
--
--   existencia(d) = saldo_hoy - suma(movimientos con fecha > d)
--
-- Se arma una rejilla par CEDIS-producto × día (para que los días sin movimiento existan: nulo
-- no es cero) y una suma de ventana hacia atrás deshace los flujos posteriores a cada día.

CREATE VIEW inventario.calendario AS
SELECT d::date AS fecha
FROM inventario.periodo p, generate_series(p.inicio, p.fin, interval '1 day') AS d;

CREATE MATERIALIZED VIEW inventario.existencia_diaria AS
WITH neto AS (            -- flujo neto por par y día
    SELECT almacen, sku, fecha, SUM(cantidad) AS neto
    FROM inventario.movimiento
    GROUP BY almacen, sku, fecha
),
rejilla AS (              -- todos los días de todos los pares, con o sin movimiento
    SELECT s.almacen, s.sku, c.fecha, s.existencia AS saldo_hoy, COALESCE(n.neto, 0) AS neto
    FROM inventario.saldo_hoy s
    CROSS JOIN inventario.calendario c
    LEFT JOIN neto n USING (almacen, sku, fecha)
),
nivel AS (                -- deshacer, hacia atrás, lo que pasó después de cada día
    SELECT almacen, sku, fecha,
           saldo_hoy - COALESCE(SUM(neto) OVER (
               PARTITION BY almacen, sku
               ORDER BY fecha DESC
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS existencia
    FROM rejilla
),
tasa AS (                 -- venta diaria del par en los días en que sí hubo existencia
    SELECT n.almacen, n.sku,
           COALESCE(v.salidas, 0)::numeric
             / NULLIF(COUNT(*) FILTER (WHERE n.existencia > 0), 0) AS venta_dia
    FROM nivel n
    LEFT JOIN (SELECT almacen, sku, -SUM(cantidad) AS salidas
               FROM inventario.movimiento WHERE tipo = 'Salida'
               GROUP BY almacen, sku) v USING (almacen, sku)
    GROUP BY n.almacen, n.sku, v.salidas
)
SELECT n.fecha, n.almacen, n.sku, n.existencia,
       n.existencia <= 0 AS en_cero,
       CASE WHEN n.existencia <= 0 THEN ROUND(COALESCE(t.venta_dia, 0), 3) ELSE 0 END AS venta_perdida_est
FROM nivel n
JOIN tasa t USING (almacen, sku);

CREATE UNIQUE INDEX existencia_diaria_pk ON inventario.existencia_diaria (almacen, sku, fecha);
COMMENT ON MATERIALIZED VIEW inventario.existencia_diaria IS
    'Existencia al cierre de cada día. Refrescar con REFRESH MATERIALIZED VIEW tras cada carga.';


-- Validación contra el conteo físico. El conteo es el universo: LEFT JOIN, porque un INNER JOIN
-- tiraría justo los pares sin existencia reconstruida que se quieren medir.
CREATE VIEW inventario.validacion AS
SELECT c.fecha, c.almacen, c.sku,
       c.conteo,
       COALESCE(e.existencia, 0)                                AS reconstruido,
       COALESCE(e.existencia, 0) - c.conteo                     AS diferencia,
       COALESCE(e.existencia, 0) = c.conteo                     AS coincide_exacto,
       (COALESCE(e.existencia, 0) <= 0) = (c.conteo <= 0)       AS coincide_cero
FROM inventario.conteo_fisico c
LEFT JOIN inventario.existencia_diaria e USING (almacen, sku, fecha);


-- Rachas de días en cero por par (huecos e islas): cada racha es un tramo continuo de días en cero.
CREATE VIEW inventario.rachas_cero AS
WITH marcados AS (
    SELECT almacen, sku, fecha,
           fecha - (ROW_NUMBER() OVER (PARTITION BY almacen, sku ORDER BY fecha))::int AS grupo
    FROM inventario.existencia_diaria
    WHERE en_cero
)
SELECT almacen, sku,
       MIN(fecha) AS desde,
       MAX(fecha) AS hasta,
       COUNT(*)   AS dias
FROM marcados
GROUP BY almacen, sku, grupo;
