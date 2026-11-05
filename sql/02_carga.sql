-- Carga de los CSV de datos/ con \copy (lado cliente de psql). Correr desde la raíz del repo.

INSERT INTO inventario.periodo VALUES ('2025-09-01', '2026-11-04');

\copy inventario.almacen  (almacen, nombre, estado)               FROM 'datos/dim_almacen.csv'   WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy inventario.producto (sku, producto, categoria, cliente)      FROM 'datos/dim_producto.csv'  WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy inventario.movimiento (fecha, almacen, sku, tipo, cantidad)  FROM 'datos/fct_movimiento.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy inventario.saldo_hoy (almacen, sku, existencia)              FROM 'datos/saldo_hoy.csv'     WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy inventario.conteo_fisico (fecha, almacen, sku, conteo)       FROM 'datos/conteo_fisico.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

-- los movimientos fuera del periodo declarado son un error de exportación, no un dato
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM inventario.movimiento m, inventario.periodo p
               WHERE m.fecha NOT BETWEEN p.inicio AND p.fin) THEN
        RAISE EXCEPTION 'Hay movimientos fuera del periodo declarado';
    END IF;
END $$;

ANALYZE inventario.movimiento;
