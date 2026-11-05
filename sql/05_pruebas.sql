-- Pruebas de integridad y de resultado. Cada fila debe decir "ok"; ON_ERROR_STOP detiene la corrida
-- si alguna falla.

CREATE TEMP TABLE prueba (nombre text, ok boolean, detalle text);

-- 1. el último día de la reconstrucción es exactamente el saldo de hoy
INSERT INTO prueba
SELECT 'último día = saldo de hoy', COUNT(*) = 0, COUNT(*) || ' pares distintos'
FROM inventario.existencia_diaria e
JOIN inventario.saldo_hoy s USING (almacen, sku)
WHERE e.fecha = (SELECT fin FROM inventario.periodo) AND e.existencia <> s.existencia;

-- 2. la rejilla está completa: pares × días
INSERT INTO prueba
SELECT 'rejilla completa',
       (SELECT COUNT(*) FROM inventario.existencia_diaria)
         = (SELECT COUNT(*) FROM inventario.saldo_hoy) * (SELECT COUNT(*) FROM inventario.calendario),
       (SELECT COUNT(*) FROM inventario.existencia_diaria) || ' filas';

-- 3. el cambio de nivel entre días consecutivos es el neto del día (la reconstrucción cuadra con el libro)
INSERT INTO prueba
WITH d AS (
    SELECT almacen, sku, fecha, existencia - LAG(existencia) OVER (PARTITION BY almacen, sku ORDER BY fecha) AS cambio
    FROM inventario.existencia_diaria
), n AS (
    SELECT almacen, sku, fecha, SUM(cantidad) AS neto FROM inventario.movimiento GROUP BY 1, 2, 3
)
SELECT 'cambio diario = neto del libro', COUNT(*) = 0, COUNT(*) || ' días que no cuadran'
FROM d LEFT JOIN n USING (almacen, sku, fecha)
WHERE d.cambio IS NOT NULL AND d.cambio <> COALESCE(n.neto, 0);

-- 4. sin existencia negativa
INSERT INTO prueba
SELECT 'sin existencia negativa', COUNT(*) = 0, COUNT(*) || ' filas'
FROM inventario.existencia_diaria WHERE existencia < 0;

-- 5. todos los pares contados se validan (el LEFT JOIN no pierde ninguno)
INSERT INTO prueba
SELECT 'validación conserva el universo del conteo',
       (SELECT COUNT(*) FROM inventario.validacion) = (SELECT COUNT(*) FROM inventario.conteo_fisico),
       (SELECT COUNT(*) FROM inventario.validacion) || ' pares';

-- 6. las rachas suman los días en cero
INSERT INTO prueba
SELECT 'rachas = días en cero',
       (SELECT SUM(dias) FROM inventario.rachas_cero) = (SELECT COUNT(*) FROM inventario.existencia_diaria WHERE en_cero),
       (SELECT COUNT(*) FROM inventario.rachas_cero) || ' rachas';

SELECT CASE WHEN ok THEN 'ok' ELSE 'FALLA' END AS resultado, nombre, detalle FROM prueba;

-- resumen de la validación, el mismo que muestra la página Validación del reporte
SELECT COUNT(*)                                                  AS pares_validados,
       ROUND(AVG(coincide_exacto::int) * 100, 1)                 AS coincidencia_exacta_pct,
       ROUND(AVG(coincide_cero::int) * 100, 1)                   AS acierto_en_cero_pct,
       ROUND(AVG(ABS(diferencia)), 2)                            AS error_medio_u
FROM inventario.validacion;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM prueba WHERE NOT ok) THEN
        RAISE EXCEPTION 'Falló al menos una prueba';
    END IF;
END $$;
