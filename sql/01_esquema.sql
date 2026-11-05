-- Esquema de origen: lo que exporta el ERP (catálogos, libro de movimientos, saldo de hoy)
-- y el conteo físico independiente. Las reglas de negocio viven en restricciones, no en la carga.

DROP SCHEMA IF EXISTS pbi CASCADE;
DROP SCHEMA IF EXISTS inventario CASCADE;
CREATE SCHEMA inventario;

CREATE TABLE inventario.periodo (
    inicio date NOT NULL,
    fin    date NOT NULL,
    CHECK (fin >= inicio)
);
COMMENT ON TABLE inventario.periodo IS 'Ventana del libro de movimientos: una sola fila.';

CREATE TABLE inventario.almacen (
    almacen varchar(3) PRIMARY KEY,
    nombre  text NOT NULL,
    estado  text NOT NULL
);

CREATE TABLE inventario.producto (
    sku       text PRIMARY KEY,
    producto  text NOT NULL,
    categoria text NOT NULL,
    cliente   text NOT NULL
);

CREATE TABLE inventario.movimiento (
    id       bigserial PRIMARY KEY,
    fecha    date NOT NULL,
    almacen  varchar(3) NOT NULL REFERENCES inventario.almacen,
    sku      text NOT NULL REFERENCES inventario.producto,
    tipo     text NOT NULL CHECK (tipo IN ('Entrada', 'Salida', 'Traspaso salida', 'Ajuste merma', 'Ajuste conteo')),
    cantidad integer NOT NULL CHECK (cantidad <> 0),
    -- el signo tiene que corresponder al tipo: una salida nunca suma
    CHECK ((tipo = 'Entrada' AND cantidad > 0)
        OR (tipo IN ('Salida', 'Traspaso salida', 'Ajuste merma') AND cantidad < 0)
        OR  tipo = 'Ajuste conteo')
);
CREATE INDEX movimiento_par_fecha ON inventario.movimiento (almacen, sku, fecha);
COMMENT ON TABLE inventario.movimiento IS 'Libro de movimientos: flujos, no niveles. + entra, - sale.';

CREATE TABLE inventario.saldo_hoy (
    almacen    varchar(3) REFERENCES inventario.almacen,
    sku        text REFERENCES inventario.producto,
    existencia integer NOT NULL,
    PRIMARY KEY (almacen, sku)
);
COMMENT ON TABLE inventario.saldo_hoy IS 'Existencia del sistema al cierre del último día del periodo.';

CREATE TABLE inventario.conteo_fisico (
    fecha   date,
    almacen varchar(3) REFERENCES inventario.almacen,
    sku     text REFERENCES inventario.producto,
    conteo  integer NOT NULL CHECK (conteo >= 0),
    PRIMARY KEY (fecha, almacen, sku)
);
COMMENT ON TABLE inventario.conteo_fisico IS 'Conteo físico hecho por otra vía: la referencia para validar.';
