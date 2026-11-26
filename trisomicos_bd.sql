-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 25-11-2026 a las 22:34:09
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `trisomicos_bd`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `caja`
--

CREATE TABLE `caja` (
  `ID_CAJA` int(11) NOT NULL,
  `ID_LOTE` int(11) NOT NULL,
  `ID_COLOR_PRODUCTO` int(11) NOT NULL,
  `LEIDA` tinyint(1) NOT NULL DEFAULT 0,
  `FECHA_LECTURA_BANDA` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `caja_pieza`
--

CREATE TABLE `caja_pieza` (
  `ID_CAJA` int(11) NOT NULL,
  `ID_PIEZA` int(11) NOT NULL,
  `CANTIDAD` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `color_producto`
--

CREATE TABLE `color_producto` (
  `ID_COLOR_PRODUCTO` int(11) NOT NULL,
  `ID_PRODUCTO` int(11) NOT NULL,
  `ID_PROVEEDOR` int(11) NOT NULL,
  `NOMBRE_COLOR` varchar(30) NOT NULL,
  `CODIGO_HEX` varchar(7) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `color_producto`
--

INSERT INTO `color_producto` (`ID_COLOR_PRODUCTO`, `ID_PRODUCTO`, `ID_PROVEEDOR`, `NOMBRE_COLOR`, `CODIGO_HEX`) VALUES
(1, 1, 1, 'AZUL', '#0057FF'),
(2, 2, 2, 'NARANJA', '#FF7A00'),
(3, 3, 3, 'VERDE', '#1FA23A'),
(4, 4, 1, 'AMARILLO', '#FFD400'),
(5, 1, 2, 'MORADO', '#7A1FA2');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `estado_lote`
--

CREATE TABLE `estado_lote` (
  `ID_ESTADO_LOTE` int(11) NOT NULL,
  `NOMBRE_ESTADO_LOTE` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `estado_lote`
--

INSERT INTO `estado_lote` (`ID_ESTADO_LOTE`, `NOMBRE_ESTADO_LOTE`) VALUES
(2, 'COMPLETO'),
(1, 'EN_RECEPCION'),
(4, 'EXCEDENTE'),
(3, 'INCOMPLETO');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `estado_oc`
--

CREATE TABLE `estado_oc` (
  `ID_ESTADO_OC` int(11) NOT NULL,
  `NOMBRE_ESTADO_OC` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `estado_oc`
--

INSERT INTO `estado_oc` (`ID_ESTADO_OC`, `NOMBRE_ESTADO_OC`) VALUES
(1, 'ACTIVA'),
(3, 'CANCELADA'),
(4, 'COMPLETADA'),
(2, 'PAUSADA');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `estado_orden_trabajo`
--

CREATE TABLE `estado_orden_trabajo` (
  `ID_ESTADO_ORDEN_TRABAJO` int(11) NOT NULL,
  `NOMBRE_ESTADO_ORDEN_TRABAJO` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `estado_orden_trabajo`
--

INSERT INTO `estado_orden_trabajo` (`ID_ESTADO_ORDEN_TRABAJO`, `NOMBRE_ESTADO_ORDEN_TRABAJO`) VALUES
(2, 'EN_PROCESO'),
(1, 'PENDIENTE'),
(3, 'RESUELTA');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `frecuencia_entrega`
--

CREATE TABLE `frecuencia_entrega` (
  `ID_FRECUENCIA` int(11) NOT NULL,
  `NOMBRE_FRECUENCIA` varchar(30) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `frecuencia_entrega`
--

INSERT INTO `frecuencia_entrega` (`ID_FRECUENCIA`, `NOMBRE_FRECUENCIA`) VALUES
(1, 'DIARIA'),
(4, 'MENSUAL'),
(3, 'QUINCENAL'),
(2, 'SEMANAL'),
(5, 'UNICA');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `lectura_banda`
--

CREATE TABLE `lectura_banda` (
  `ID_LECTURA` int(11) NOT NULL,
  `ID_CAJA` int(11) NOT NULL,
  `TIMESTAMP_LECTURA` datetime NOT NULL,
  `RESULTADO` varchar(10) NOT NULL
) ;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `lote_recepcion`
--

CREATE TABLE `lote_recepcion` (
  `ID_LOTE` int(11) NOT NULL,
  `ID_OC` int(11) NOT NULL,
  `ID_ESTADO_LOTE` int(11) NOT NULL,
  `FECHA_RECEPCION` datetime NOT NULL,
  `CANTIDAD_CAJAS_ESPERADA` int(11) NOT NULL,
  `CANTIDAD_CAJAS_CONTADA` int(11) NOT NULL DEFAULT 0,
  `ID_USUARIO_RECEPCION` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `lote_recepcion`
--

INSERT INTO `lote_recepcion` (`ID_LOTE`, `ID_OC`, `ID_ESTADO_LOTE`, `FECHA_RECEPCION`, `CANTIDAD_CAJAS_ESPERADA`, `CANTIDAD_CAJAS_CONTADA`, `ID_USUARIO_RECEPCION`) VALUES
(1, 1, 1, '2026-11-10 09:00:00', 5, 0, 1),
(2, 2, 1, '2026-11-10 09:30:00', 8, 0, 1),
(3, 3, 1, '2026-11-10 10:00:00', 6, 0, 1),
(4, 4, 1, '2026-11-10 10:30:00', 7, 0, 1),
(5, 5, 1, '2026-11-10 11:00:00', 4, 0, 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `orden_compra`
--

CREATE TABLE `orden_compra` (
  `ID_OC` int(11) NOT NULL,
  `ID_PROVEEDOR` int(11) NOT NULL,
  `ID_ESTADO_OC` int(11) NOT NULL,
  `ID_FRECUENCIA` int(11) NOT NULL,
  `FECHA_ALTA` date NOT NULL,
  `FECHA_PROXIMA_ENTREGA` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `orden_compra`
--

INSERT INTO `orden_compra` (`ID_OC`, `ID_PROVEEDOR`, `ID_ESTADO_OC`, `ID_FRECUENCIA`, `FECHA_ALTA`, `FECHA_PROXIMA_ENTREGA`) VALUES
(1, 1, 1, 2, '2026-11-01', '2026-11-08'),
(2, 2, 1, 2, '2026-11-01', '2026-11-08'),
(3, 3, 1, 4, '2026-11-01', '2026-12-01'),
(4, 1, 1, 2, '2026-11-01', '2026-11-08'),
(5, 2, 1, 5, '2026-11-01', NULL);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `orden_compra_detalle`
--

CREATE TABLE `orden_compra_detalle` (
  `ID_OC_DETALLE` int(11) NOT NULL,
  `ID_OC` int(11) NOT NULL,
  `ID_PRODUCTO` int(11) NOT NULL,
  `CANTIDAD_CAJAS_ESPERADA` int(11) NOT NULL,
  `PIEZAS_POR_CAJA` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `orden_compra_detalle`
--

INSERT INTO `orden_compra_detalle` (`ID_OC_DETALLE`, `ID_OC`, `ID_PRODUCTO`, `CANTIDAD_CAJAS_ESPERADA`, `PIEZAS_POR_CAJA`) VALUES
(1, 1, 1, 5, 500),
(2, 2, 2, 8, 100),
(3, 3, 3, 6, 50),
(4, 4, 4, 7, 20),
(5, 5, 1, 4, 500);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `orden_trabajo`
--

CREATE TABLE `orden_trabajo` (
  `ID_ORDEN_TRABAJO` int(11) NOT NULL,
  `ID_TIPO_INCIDENCIA` int(11) NOT NULL,
  `ID_ESTADO_ORDEN_TRABAJO` int(11) NOT NULL,
  `ID_LOTE` int(11) DEFAULT NULL,
  `ID_CAJA` int(11) DEFAULT NULL,
  `FECHA_GENERACION` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `pieza`
--

CREATE TABLE `pieza` (
  `ID_PIEZA` int(11) NOT NULL,
  `NOMBRE_PIEZA` varchar(100) NOT NULL,
  `PROPIEDADES` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`PROPIEDADES`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `pieza`
--

INSERT INTO `pieza` (`ID_PIEZA`, `NOMBRE_PIEZA`, `PROPIEDADES`) VALUES
(1, 'TORNILLO_M6X20', '{\"material\": \"ACERO\", \"rosca\": \"M6\", \"longitud_mm\": 20}'),
(2, 'RODAMIENTO_608ZZ', '{\"material\": \"ACERO_CROMADO\", \"diametro_mm\": 8}');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `producto`
--

CREATE TABLE `producto` (
  `ID_PRODUCTO` int(11) NOT NULL,
  `NOMBRE_PRODUCTO` varchar(100) NOT NULL,
  `UNIDAD_MEDIDA` varchar(30) DEFAULT NULL,
  `PIEZAS_POR_CAJA_ESTANDAR` int(11) DEFAULT NULL,
  `ACTIVO` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `producto`
--

INSERT INTO `producto` (`ID_PRODUCTO`, `NOMBRE_PRODUCTO`, `UNIDAD_MEDIDA`, `PIEZAS_POR_CAJA_ESTANDAR`, `ACTIVO`) VALUES
(1, 'TORN_M6X20', 'PCS', 500, 1),
(2, 'ROD_608ZZ', 'PCS', 100, 1),
(3, 'CABLE_18AWG', 'M', 50, 1),
(4, 'SENSOR_IND_M12', 'PCS', 20, 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `proveedor`
--

CREATE TABLE `proveedor` (
  `ID_PROVEEDOR` int(11) NOT NULL,
  `NOMBRE_PROVEEDOR` varchar(100) NOT NULL,
  `CONTACTO` varchar(100) DEFAULT NULL,
  `TELEFONO` varchar(20) DEFAULT NULL,
  `ACTIVO` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `proveedor`
--

INSERT INTO `proveedor` (`ID_PROVEEDOR`, `NOMBRE_PROVEEDOR`, `CONTACTO`, `TELEFONO`, `ACTIVO`) VALUES
(1, 'PROV_NORTE', 'LUIS HERNANDEZ', '2281234567', 1),
(2, 'PROV_GOLFO', 'ANA MARTINEZ', '2297654321', 1),
(3, 'PROV_IND_MX', 'JORGE RAMIREZ', '2299988776', 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tipo_incidencia`
--

CREATE TABLE `tipo_incidencia` (
  `ID_TIPO_INCIDENCIA` int(11) NOT NULL,
  `NOMBRE_TIPO_INCIDENCIA` varchar(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `tipo_incidencia`
--

INSERT INTO `tipo_incidencia` (`ID_TIPO_INCIDENCIA`, `NOMBRE_TIPO_INCIDENCIA`) VALUES
(5, 'CAJA_SIN_LECTURA'),
(2, 'COMUNICACION_PROVEEDOR'),
(4, 'LOTE_EXCEDENTE'),
(3, 'LOTE_INCOMPLETO'),
(1, 'REVISION_CAJA_RETENIDA');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `usuario`
--

CREATE TABLE `usuario` (
  `ID_USUARIO` int(11) NOT NULL,
  `NOMBRE` varchar(100) NOT NULL,
  `ROL` varchar(20) NOT NULL,
  `ACTIVO` tinyint(1) NOT NULL DEFAULT 1
) ;

--
-- Volcado de datos para la tabla `usuario`
--

INSERT INTO `usuario` (`ID_USUARIO`, `NOMBRE`, `ROL`, `ACTIVO`) VALUES
(1, 'MARIA LOPEZ', 'ALMACENISTA', 1),
(2, 'CARLOS DIAZ', 'SUPERVISOR', 1);

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `caja`
--
ALTER TABLE `caja`
  ADD PRIMARY KEY (`ID_CAJA`),
  ADD KEY `FK_CAJA_LOTE` (`ID_LOTE`),
  ADD KEY `FK_CAJA_COLORPROD` (`ID_COLOR_PRODUCTO`);

--
-- Indices de la tabla `caja_pieza`
--
ALTER TABLE `caja_pieza`
  ADD PRIMARY KEY (`ID_CAJA`,`ID_PIEZA`),
  ADD KEY `FK_CAJAPIEZA_PIEZA` (`ID_PIEZA`);

--
-- Indices de la tabla `color_producto`
--
ALTER TABLE `color_producto`
  ADD PRIMARY KEY (`ID_COLOR_PRODUCTO`),
  ADD UNIQUE KEY `NOMBRE_COLOR` (`NOMBRE_COLOR`),
  ADD UNIQUE KEY `UQ_COLOR_PRODUCTO_PROVEEDOR` (`ID_PRODUCTO`,`ID_PROVEEDOR`),
  ADD KEY `FK_COLORPROD_PROVEEDOR` (`ID_PROVEEDOR`);

--
-- Indices de la tabla `estado_lote`
--
ALTER TABLE `estado_lote`
  ADD PRIMARY KEY (`ID_ESTADO_LOTE`),
  ADD UNIQUE KEY `NOMBRE_ESTADO_LOTE` (`NOMBRE_ESTADO_LOTE`);

--
-- Indices de la tabla `estado_oc`
--
ALTER TABLE `estado_oc`
  ADD PRIMARY KEY (`ID_ESTADO_OC`),
  ADD UNIQUE KEY `NOMBRE_ESTADO_OC` (`NOMBRE_ESTADO_OC`);

--
-- Indices de la tabla `estado_orden_trabajo`
--
ALTER TABLE `estado_orden_trabajo`
  ADD PRIMARY KEY (`ID_ESTADO_ORDEN_TRABAJO`),
  ADD UNIQUE KEY `NOMBRE_ESTADO_ORDEN_TRABAJO` (`NOMBRE_ESTADO_ORDEN_TRABAJO`);

--
-- Indices de la tabla `frecuencia_entrega`
--
ALTER TABLE `frecuencia_entrega`
  ADD PRIMARY KEY (`ID_FRECUENCIA`),
  ADD UNIQUE KEY `NOMBRE_FRECUENCIA` (`NOMBRE_FRECUENCIA`);

--
-- Indices de la tabla `lectura_banda`
--
ALTER TABLE `lectura_banda`
  ADD PRIMARY KEY (`ID_LECTURA`),
  ADD KEY `FK_LECTURA_CAJA` (`ID_CAJA`);

--
-- Indices de la tabla `lote_recepcion`
--
ALTER TABLE `lote_recepcion`
  ADD PRIMARY KEY (`ID_LOTE`),
  ADD KEY `FK_LOTE_OC` (`ID_OC`),
  ADD KEY `FK_LOTE_ESTADO` (`ID_ESTADO_LOTE`),
  ADD KEY `FK_LOTE_USUARIO` (`ID_USUARIO_RECEPCION`);

--
-- Indices de la tabla `orden_compra`
--
ALTER TABLE `orden_compra`
  ADD PRIMARY KEY (`ID_OC`),
  ADD KEY `FK_OC_PROVEEDOR` (`ID_PROVEEDOR`),
  ADD KEY `FK_OC_ESTADO` (`ID_ESTADO_OC`),
  ADD KEY `FK_OC_FRECUENCIA` (`ID_FRECUENCIA`);

--
-- Indices de la tabla `orden_compra_detalle`
--
ALTER TABLE `orden_compra_detalle`
  ADD PRIMARY KEY (`ID_OC_DETALLE`),
  ADD KEY `FK_OCDET_OC` (`ID_OC`),
  ADD KEY `FK_OCDET_PRODUCTO` (`ID_PRODUCTO`);

--
-- Indices de la tabla `orden_trabajo`
--
ALTER TABLE `orden_trabajo`
  ADD PRIMARY KEY (`ID_ORDEN_TRABAJO`),
  ADD KEY `FK_OT_TIPO` (`ID_TIPO_INCIDENCIA`),
  ADD KEY `FK_OT_ESTADO` (`ID_ESTADO_ORDEN_TRABAJO`),
  ADD KEY `FK_OT_LOTE` (`ID_LOTE`),
  ADD KEY `FK_OT_CAJA` (`ID_CAJA`);

--
-- Indices de la tabla `pieza`
--
ALTER TABLE `pieza`
  ADD PRIMARY KEY (`ID_PIEZA`),
  ADD UNIQUE KEY `NOMBRE_PIEZA` (`NOMBRE_PIEZA`);

--
-- Indices de la tabla `producto`
--
ALTER TABLE `producto`
  ADD PRIMARY KEY (`ID_PRODUCTO`),
  ADD UNIQUE KEY `NOMBRE_PRODUCTO` (`NOMBRE_PRODUCTO`);

--
-- Indices de la tabla `proveedor`
--
ALTER TABLE `proveedor`
  ADD PRIMARY KEY (`ID_PROVEEDOR`),
  ADD UNIQUE KEY `NOMBRE_PROVEEDOR` (`NOMBRE_PROVEEDOR`);

--
-- Indices de la tabla `tipo_incidencia`
--
ALTER TABLE `tipo_incidencia`
  ADD PRIMARY KEY (`ID_TIPO_INCIDENCIA`),
  ADD UNIQUE KEY `NOMBRE_TIPO_INCIDENCIA` (`NOMBRE_TIPO_INCIDENCIA`);

--
-- Indices de la tabla `usuario`
--
ALTER TABLE `usuario`
  ADD PRIMARY KEY (`ID_USUARIO`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `caja`
--
ALTER TABLE `caja`
  MODIFY `ID_CAJA` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `color_producto`
--
ALTER TABLE `color_producto`
  MODIFY `ID_COLOR_PRODUCTO` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `estado_lote`
--
ALTER TABLE `estado_lote`
  MODIFY `ID_ESTADO_LOTE` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT de la tabla `estado_oc`
--
ALTER TABLE `estado_oc`
  MODIFY `ID_ESTADO_OC` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT de la tabla `estado_orden_trabajo`
--
ALTER TABLE `estado_orden_trabajo`
  MODIFY `ID_ESTADO_ORDEN_TRABAJO` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT de la tabla `frecuencia_entrega`
--
ALTER TABLE `frecuencia_entrega`
  MODIFY `ID_FRECUENCIA` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `lectura_banda`
--
ALTER TABLE `lectura_banda`
  MODIFY `ID_LECTURA` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `lote_recepcion`
--
ALTER TABLE `lote_recepcion`
  MODIFY `ID_LOTE` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `orden_compra`
--
ALTER TABLE `orden_compra`
  MODIFY `ID_OC` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `orden_compra_detalle`
--
ALTER TABLE `orden_compra_detalle`
  MODIFY `ID_OC_DETALLE` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `orden_trabajo`
--
ALTER TABLE `orden_trabajo`
  MODIFY `ID_ORDEN_TRABAJO` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `pieza`
--
ALTER TABLE `pieza`
  MODIFY `ID_PIEZA` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT de la tabla `producto`
--
ALTER TABLE `producto`
  MODIFY `ID_PRODUCTO` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT de la tabla `proveedor`
--
ALTER TABLE `proveedor`
  MODIFY `ID_PROVEEDOR` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT de la tabla `tipo_incidencia`
--
ALTER TABLE `tipo_incidencia`
  MODIFY `ID_TIPO_INCIDENCIA` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `usuario`
--
ALTER TABLE `usuario`
  MODIFY `ID_USUARIO` int(11) NOT NULL AUTO_INCREMENT;

--
-- Restricciones para tablas volcadas
--

--
-- Filtros para la tabla `caja`
--
ALTER TABLE `caja`
  ADD CONSTRAINT `FK_CAJA_COLORPROD` FOREIGN KEY (`ID_COLOR_PRODUCTO`) REFERENCES `color_producto` (`ID_COLOR_PRODUCTO`),
  ADD CONSTRAINT `FK_CAJA_LOTE` FOREIGN KEY (`ID_LOTE`) REFERENCES `lote_recepcion` (`ID_LOTE`);

--
-- Filtros para la tabla `caja_pieza`
--
ALTER TABLE `caja_pieza`
  ADD CONSTRAINT `FK_CAJAPIEZA_CAJA` FOREIGN KEY (`ID_CAJA`) REFERENCES `caja` (`ID_CAJA`),
  ADD CONSTRAINT `FK_CAJAPIEZA_PIEZA` FOREIGN KEY (`ID_PIEZA`) REFERENCES `pieza` (`ID_PIEZA`);

--
-- Filtros para la tabla `color_producto`
--
ALTER TABLE `color_producto`
  ADD CONSTRAINT `FK_COLORPROD_PRODUCTO` FOREIGN KEY (`ID_PRODUCTO`) REFERENCES `producto` (`ID_PRODUCTO`),
  ADD CONSTRAINT `FK_COLORPROD_PROVEEDOR` FOREIGN KEY (`ID_PROVEEDOR`) REFERENCES `proveedor` (`ID_PROVEEDOR`);

--
-- Filtros para la tabla `lectura_banda`
--
ALTER TABLE `lectura_banda`
  ADD CONSTRAINT `FK_LECTURA_CAJA` FOREIGN KEY (`ID_CAJA`) REFERENCES `caja` (`ID_CAJA`);

--
-- Filtros para la tabla `lote_recepcion`
--
ALTER TABLE `lote_recepcion`
  ADD CONSTRAINT `FK_LOTE_ESTADO` FOREIGN KEY (`ID_ESTADO_LOTE`) REFERENCES `estado_lote` (`ID_ESTADO_LOTE`),
  ADD CONSTRAINT `FK_LOTE_OC` FOREIGN KEY (`ID_OC`) REFERENCES `orden_compra` (`ID_OC`),
  ADD CONSTRAINT `FK_LOTE_USUARIO` FOREIGN KEY (`ID_USUARIO_RECEPCION`) REFERENCES `usuario` (`ID_USUARIO`);

--
-- Filtros para la tabla `orden_compra`
--
ALTER TABLE `orden_compra`
  ADD CONSTRAINT `FK_OC_ESTADO` FOREIGN KEY (`ID_ESTADO_OC`) REFERENCES `estado_oc` (`ID_ESTADO_OC`),
  ADD CONSTRAINT `FK_OC_FRECUENCIA` FOREIGN KEY (`ID_FRECUENCIA`) REFERENCES `frecuencia_entrega` (`ID_FRECUENCIA`),
  ADD CONSTRAINT `FK_OC_PROVEEDOR` FOREIGN KEY (`ID_PROVEEDOR`) REFERENCES `proveedor` (`ID_PROVEEDOR`);

--
-- Filtros para la tabla `orden_compra_detalle`
--
ALTER TABLE `orden_compra_detalle`
  ADD CONSTRAINT `FK_OCDET_OC` FOREIGN KEY (`ID_OC`) REFERENCES `orden_compra` (`ID_OC`),
  ADD CONSTRAINT `FK_OCDET_PRODUCTO` FOREIGN KEY (`ID_PRODUCTO`) REFERENCES `producto` (`ID_PRODUCTO`);

--
-- Filtros para la tabla `orden_trabajo`
--
ALTER TABLE `orden_trabajo`
  ADD CONSTRAINT `FK_OT_CAJA` FOREIGN KEY (`ID_CAJA`) REFERENCES `caja` (`ID_CAJA`),
  ADD CONSTRAINT `FK_OT_ESTADO` FOREIGN KEY (`ID_ESTADO_ORDEN_TRABAJO`) REFERENCES `estado_orden_trabajo` (`ID_ESTADO_ORDEN_TRABAJO`),
  ADD CONSTRAINT `FK_OT_LOTE` FOREIGN KEY (`ID_LOTE`) REFERENCES `lote_recepcion` (`ID_LOTE`),
  ADD CONSTRAINT `FK_OT_TIPO` FOREIGN KEY (`ID_TIPO_INCIDENCIA`) REFERENCES `tipo_incidencia` (`ID_TIPO_INCIDENCIA`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
