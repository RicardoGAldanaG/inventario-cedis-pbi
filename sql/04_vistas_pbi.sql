-- Capa de consumo para Power BI: mismas tablas y columnas que el modelo, una vista por tabla.
-- El modelo solo lee de aquí; si cambia el origen, cambian estas vistas y no el reporte.

CREATE SCHEMA pbi;

CREATE VIEW pbi.dim_fecha AS
SELECT c.fecha,
       EXTRACT(year FROM c.fecha)::int                        AS anio,
       EXTRACT(month FROM c.fecha)::int                       AS mes,
       to_char(c.fecha, 'YYYY-MM')                            AS anio_mes,
       (ARRAY['enero','febrero','marzo','abril','mayo','junio','julio','agosto',
              'septiembre','octubre','noviembre','diciembre'])[EXTRACT(month FROM c.fecha)::int] AS nombre_mes,
       EXTRACT(isodow FROM c.fecha)::int                      AS dia_semana,
       (ARRAY['lunes','martes','miércoles','jueves','viernes','sábado','domingo'])[EXTRACT(isodow FROM c.fecha)::int] AS nombre_dia,
       EXTRACT(isodow FROM c.fecha) >= 6                      AS es_fin_de_semana
FROM inventario.calendario c;

CREATE VIEW pbi.dim_almacen AS
SELECT almacen, nombre, estado FROM inventario.almacen;

CREATE VIEW pbi.dim_producto AS
SELECT sku, producto, categoria, cliente FROM inventario.producto;

CREATE VIEW pbi.fct_movimiento AS
SELECT fecha, almacen, sku, tipo, cantidad FROM inventario.movimiento;

CREATE VIEW pbi.fct_existencia_diaria AS
SELECT fecha, almacen, sku, existencia, en_cero, venta_perdida_est::double precision AS venta_perdida_est
FROM inventario.existencia_diaria;

CREATE VIEW pbi.fct_validacion AS
SELECT almacen, sku, conteo, reconstruido, diferencia, coincide_exacto, coincide_cero
FROM inventario.validacion;

CREATE VIEW pbi.fct_rachas_cero AS
SELECT almacen, sku, desde, hasta, dias FROM inventario.rachas_cero;
