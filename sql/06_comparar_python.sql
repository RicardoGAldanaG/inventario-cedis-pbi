-- Compara, fila por fila, la reconstrucción en SQL contra la del script de Python
-- (datos/fct_existencia_diaria.csv y datos/fct_validacion.csv). Correr desde la raíz del repo:
--   psql -h localhost -p 5433 -U postgres -d inventario_cedis -v ON_ERROR_STOP=1 -f sql/06_comparar_python.sql

CREATE TEMP TABLE py_existencia (fecha date, almacen text, sku text, existencia int, en_cero boolean, venta_perdida_est numeric);
\copy py_existencia FROM 'datos/fct_existencia_diaria.csv' WITH (FORMAT csv, HEADER true)
CREATE TEMP TABLE py_validacion (almacen text, sku text, conteo int, reconstruido int, diferencia int, coincide_exacto boolean, coincide_cero boolean);
\copy py_validacion FROM 'datos/fct_validacion.csv' WITH (FORMAT csv, HEADER true)

SELECT 'existencia: filas solo en SQL' AS comparacion, COUNT(*) AS filas FROM (
    SELECT fecha, almacen, sku, existencia, en_cero FROM inventario.existencia_diaria
    EXCEPT SELECT fecha, almacen, sku, existencia, en_cero FROM py_existencia) x
UNION ALL
SELECT 'existencia: filas solo en Python', COUNT(*) FROM (
    SELECT fecha, almacen, sku, existencia, en_cero FROM py_existencia
    EXCEPT SELECT fecha, almacen, sku, existencia, en_cero FROM inventario.existencia_diaria) x
UNION ALL
SELECT 'venta perdida: diferencias > 0.001', COUNT(*)
FROM inventario.existencia_diaria s JOIN py_existencia p USING (fecha, almacen, sku)
WHERE ABS(s.venta_perdida_est - p.venta_perdida_est) > 0.001
UNION ALL
SELECT 'validación: filas distintas', COUNT(*) FROM (
    SELECT almacen, sku, conteo, reconstruido, diferencia, coincide_exacto, coincide_cero FROM inventario.validacion
    EXCEPT SELECT * FROM py_validacion) x;
