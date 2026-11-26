import base64
import io
import os
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import pymysql
import qrcode
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

# ==============================================================================
# CONFIGURACION GENERAL - ORANGE PI ZERO 2W (MARIADB trisomicos_bd + VISION + IOT)
# ==============================================================================
app = FastAPI(title="CEDIS IoT Zero 2W - Version Final Integrada")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "app_user"),
    "password": os.getenv("DB_PASS", "Almacen2026!"),
    "database": os.getenv("DB_NAME", "trisomicos_bd"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickets_generados")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

# Mapeo de colores HSV (de la version Windows)
COLOR_RANGES_HSV = {
    "AZUL":     {"lower": np.array([92, 65, 65]),   "upper": np.array([122, 255, 255]), "bgr": (255, 120, 0),  "hex": "#2563EB"},
    "MORADO":   {"lower": np.array([123, 55, 50]),  "upper": np.array([158, 255, 255]), "bgr": (180, 50, 140), "hex": "#9333EA"},
    "VERDE":    {"lower": np.array([42, 55, 60]),   "upper": np.array([88, 255, 255]),  "bgr": (60, 180, 40),  "hex": "#16A34A"},
    "AMARILLO": {"lower": np.array([22, 70, 80]),   "upper": np.array([38, 255, 255]),  "bgr": (0, 220, 255),  "hex": "#EAB308"},
    "NARANJA":  {"lower": np.array([6, 75, 85]),    "upper": np.array([21, 255, 255]),  "bgr": (0, 130, 255),  "hex": "#F97316"},
}

ACTIVE_SESSION: Dict[str, Any] = {
    "id_lote": 1,
    "auto_scan_enabled": True,
    "last_event": "Sistema Zero 2W listo. Coloca una caja/etiqueta en la cuadricula roja central.",
    "last_route": "STANDBY",
    "servo_activado": "NINGUNO (NORMAL)",
    "conteo_actual": "0 / 0",
    "ultimo_comando_esp32": {"servo": "NINGUNO", "ruta": "NORMAL", "timestamp": None},
}


# ==============================================================================
# UTILIDADES DE BASE DE DATOS (MARIADB trisomicos_bd)
# ==============================================================================
def norm_sku(val: Optional[str]) -> str:
    return (val or "").strip().upper().replace("-", "_")


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def ensure_runtime_tables_and_catalogs():
    """
    Asegura compatibilidad con el esquema real de trisomicos_bd (MariaDB)
    y crea tablas auxiliares si no existen, evitando errores de llaves foraneas
    o columnas faltantes.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Tabla auxiliar para historico de tickets generados en la 2W
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets_simulados (
                    ID_TICKET INT AUTO_INCREMENT PRIMARY KEY,
                    TICKET_ID VARCHAR(50) NOT NULL UNIQUE,
                    ID_OC INT NULL,
                    ID_LOTE INT NULL,
                    PO_ID VARCHAR(30) NOT NULL,
                    SUPPLIER VARCHAR(120) NOT NULL,
                    SKU VARCHAR(60) NOT NULL,
                    UNIT VARCHAR(20) NOT NULL,
                    ORDERED_QTY INT NOT NULL,
                    RECEIVED_QTY INT NOT NULL,
                    MEASURED_QTY INT NOT NULL,
                    DELTA_VS_ORDER INT NOT NULL,
                    UNIT_COST_MXN DECIMAL(10,2) NULL,
                    LOT VARCHAR(40) NOT NULL,
                    SCENARIO VARCHAR(50) NOT NULL,
                    STATUS VARCHAR(50) NOT NULL,
                    RECOMMENDED_ACTION VARCHAR(160) NOT NULL,
                    LINKED_WO VARCHAR(40) NULL,
                    CREATED_AT DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
            # Asegurar catalogos minimos en tipo_incidencia y estado_orden_trabajo
            cur.execute("SELECT COUNT(*) AS n FROM tipo_incidencia")
            if cur.fetchone()["n"] == 0:
                cur.executemany(
                    "INSERT IGNORE INTO tipo_incidencia (ID_TIPO_INCIDENCIA, NOMBRE_TIPO_INCIDENCIA) VALUES (%s, %s)",
                    [
                        (1, "REVISION_CAJA_RETENIDA"),
                        (2, "COMUNICACION_PROVEEDOR"),
                        (3, "LOTE_INCOMPLETO"),
                        (4, "LOTE_EXCEDENTE"),
                        (5, "CAJA_SIN_LECTURA"),
                    ],
                )
            cur.execute("SELECT COUNT(*) AS n FROM estado_orden_trabajo")
            if cur.fetchone()["n"] == 0:
                cur.executemany(
                    "INSERT IGNORE INTO estado_orden_trabajo (ID_ESTADO_ORDEN_TRABAJO, NOMBRE_ESTADO_ORDEN_TRABAJO) VALUES (%s, %s)",
                    [(1, "PENDIENTE"), (2, "EN_PROCESO"), (3, "RESUELTA")],
                )
        conn.commit()


def sincronizar_conteo_lote(id_lote: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT CANTIDAD_CAJAS_CONTADA, CANTIDAD_CAJAS_ESPERADA FROM lote_recepcion WHERE ID_LOTE = %s",
                    (id_lote,),
                )
                row = cur.fetchone()
        if row:
            txt = f"{row['CANTIDAD_CAJAS_CONTADA']} / {row['CANTIDAD_CAJAS_ESPERADA']}"
            ACTIVE_SESSION["conteo_actual"] = txt
            vision.lote_conteo_texto = txt
    except Exception as exc:
        ACTIVE_SESSION["last_event"] = f"Aviso sincronizando lote {id_lote}: {exc}"


# ==============================================================================
# MOTOR DE VISION ARTIFICIAL (HSV + QR + CUADRICULAS DE SERVO 1 Y SERVO 2)
# Optimizado para Orange Pi Zero 2W (V4L2 en Linux, hilos ligeros, 640x480)
# ==============================================================================
class VisionSystem:
    def __init__(self, on_detection_callback=None):
        self.cap = None
        self.running = False
        self.lock = threading.Lock()
        self.raw_jpeg: Optional[bytes] = None
        self.filtered_jpeg: Optional[bytes] = None
        self.on_detection_callback = on_detection_callback
        self.qr_detector = cv2.QRCodeDetector()

        self.current_color = "NINGUNO"
        self.current_qr = "SIN_QR"
        self.active_color_filter = "TODOS"
        self.last_trigger_time = 0.0
        self.cooldown_seconds = 2.8

        self.servo_state = "NINGUNO"
        self.servo_label = "REPOSO (PASA NORMAL)"
        self.lote_conteo_texto = "0 / 0"
        self.flash_until = 0.0
        self.camera_online = False

    def start(self, camera_index: int = 0):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._loop, args=(camera_index,), daemon=True).start()

    def stop(self):
        self.running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass

    def _open_camera(self, preferred_idx: int):
        # En Linux (DietPi / Orange Pi) V4L2 es el backend nativo; prueba indice preferido y fallback 0/1
        indices = [preferred_idx] + [i for i in (0, 1, 2) if i != preferred_idx]
        for idx in indices:
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2) if hasattr(cv2, "CAP_V4L2") else cv2.VideoCapture(idx)
            if not cap.isOpened():
                cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 20)
                ret, _ = cap.read()
                if ret:
                    self.camera_online = True
                    return cap
            cap.release()
        self.camera_online = False
        return None

    def _make_placeholder(self, text: str) -> bytes:
        img = np.zeros((360, 480, 3), dtype=np.uint8)
        img[:] = (15, 23, 42)
        cv2.rectangle(img, (16, 16), (464, 344), (56, 189, 248), 2)
        cv2.putText(img, text, (34, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)
        cv2.putText(img, "Usa botones de simulacion o conecta camara USB", (34, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1)
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return buf.tobytes()

    def _draw_red_grids(self, img, now: float):
        h, w = img.shape[:2]

        # 1. Cuadricula Roja Central: ZONA DE DISPARO / PASO DE CAJA
        x1, y1 = int(w * 0.30), int(h * 0.28)
        x2, y2 = int(w * 0.70), int(h * 0.78)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.line(img, (mid_x, y1), (mid_x, y2), (0, 0, 180), 1)
        cv2.line(img, (x1, mid_y), (x2, mid_y), (0, 0, 180), 1)
        cv2.putText(img, "ZONA DISPARO BANDA", (x1 + 8, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 255), 2)

        # 2. Cuadricula Roja Izquierda: SERVO 1 (CAJA DANADA)
        s1_x1, s1_y1, s1_x2, s1_y2 = 12, int(h * 0.32), int(w * 0.26), int(h * 0.74)
        s1_active = (self.servo_state == "SERVO_1") and (now < self.flash_until)
        if s1_active:
            overlay = img.copy()
            cv2.rectangle(overlay, (s1_x1, s1_y1), (s1_x2, s1_y2), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)
        cv2.rectangle(img, (s1_x1, s1_y1), (s1_x2, s1_y2), (0, 0, 255), 2)
        cv2.putText(img, "SERVO 1", (s1_x1 + 10, s1_y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255) if s1_active else (0, 0, 255), 2)
        cv2.putText(img, "DANADA", (s1_x1 + 10, s1_y1 + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 255), 1)
        cv2.putText(img, "ACTIVO!" if s1_active else "OFF", (s1_x1 + 10, s1_y2 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255) if s1_active else (120, 120, 120), 2)

        # 3. Cuadricula Roja Derecha: SERVO 2 (PRODUCTO NO ESPERADO / DUPLICADO)
        s2_x1, s2_y1, s2_x2, s2_y2 = int(w * 0.74), int(h * 0.32), w - 12, int(h * 0.74)
        s2_active = (self.servo_state == "SERVO_2") and (now < self.flash_until)
        if s2_active:
            overlay = img.copy()
            cv2.rectangle(overlay, (s2_x1, s2_y1), (s2_x2, s2_y2), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)
        cv2.rectangle(img, (s2_x1, s2_y1), (s2_x2, s2_y2), (0, 0, 255), 2)
        cv2.putText(img, "SERVO 2", (s2_x1 + 10, s2_y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255) if s2_active else (0, 0, 255), 2)
        cv2.putText(img, "NO ESPERADO", (s2_x1 + 6, s2_y1 + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 200, 255), 1)
        cv2.putText(img, "ACTIVO!" if s2_active else "OFF", (s2_x1 + 10, s2_y2 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255) if s2_active else (120, 120, 120), 2)

        # 4. Barra inferior de estado
        cv2.rectangle(img, (0, h - 42), (w, h), (15, 23, 42), -1)
        paso_color = (0, 255, 0) if now < self.flash_until else (0, 220, 255)
        texto_paso = ">>> CAJA REGISTRADA - PUEDE PASAR <<<" if now < self.flash_until else "COLOCA ETIQUETA EN CUADRICULA CENTRAL"
        cv2.putText(img, texto_paso, (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.48, paso_color, 2)
        cv2.putText(img, f"CONTEO: {self.lote_conteo_texto}", (w - 175, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    def _loop(self, preferred_idx: int):
        kernel = np.ones((5, 5), np.uint8)
        last_retry = 0.0
        while self.running:
            now = time.time()
            if self.cap is None or not self.cap.isOpened():
                if now - last_retry > 4.0:
                    last_retry = now
                    self.cap = self._open_camera(preferred_idx)
                if self.cap is None:
                    placeholder = self._make_placeholder("Camara USB no detectada")
                    with self.lock:
                        self.raw_jpeg = placeholder
                        self.filtered_jpeg = placeholder
                    time.sleep(0.5)
                    continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.cap.release()
                self.cap = None
                self.camera_online = False
                time.sleep(0.2)
                continue

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            raw_display = frame.copy()
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            roi_x1, roi_y1 = int(w * 0.30), int(h * 0.28)
            roi_x2, roi_y2 = int(w * 0.70), int(h * 0.78)

            qr_text = ""
            try:
                data, bbox, _ = self.qr_detector.detectAndDecode(frame)
                if data:
                    qr_text = data.strip()
                    if bbox is not None:
                        pts = bbox.astype(int).reshape(-1, 2)
                        cv2.polylines(raw_display, [pts], True, (0, 255, 0), 3)
            except Exception:
                pass

            combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            detected_color = "NINGUNO"
            in_trigger_zone = False
            max_area = 2200

            colors_to_scan = (
                COLOR_RANGES_HSV.items()
                if self.active_color_filter == "TODOS"
                else [(self.active_color_filter, COLOR_RANGES_HSV[self.active_color_filter])]
            )

            for color_name, cfg in colors_to_scan:
                mask = cv2.inRange(hsv, cfg["lower"], cfg["upper"])
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)
                combined_mask = cv2.bitwise_or(combined_mask, mask)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area > max_area:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        cx, cy = x + bw // 2, y + bh // 2
                        dentro_roi = (roi_x1 <= cx <= roi_x2) and (roi_y1 <= cy <= roi_y2)
                        if dentro_roi:
                            max_area = area
                            detected_color = color_name
                            in_trigger_zone = True

                        cv2.rectangle(raw_display, (x, y), (x + bw, y + bh), cfg["bgr"], 3 if dentro_roi else 1)
                        cv2.circle(raw_display, (cx, cy), 5, (0, 0, 255) if dentro_roi else (200, 200, 200), -1)
                        cv2.putText(
                            raw_display,
                            f"{color_name}" + (" [EN ZONA]" if dentro_roi else ""),
                            (x, max(20, y - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.52,
                            cfg["bgr"],
                            2,
                        )

            filtered_display = cv2.bitwise_and(frame, frame, mask=combined_mask)
            self._draw_red_grids(filtered_display, now)
            cv2.rectangle(raw_display, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 0, 255), 2)
            cv2.putText(
                filtered_display,
                f"FILTRO [{self.active_color_filter}] | COLOR: {detected_color} | {self.servo_label}",
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (0, 255, 255),
                2,
            )

            self.current_color = detected_color
            self.current_qr = qr_text if qr_text else "SIN_QR"

            if ((in_trigger_zone and detected_color != "NINGUNO") or qr_text) and (
                now - self.last_trigger_time > self.cooldown_seconds
            ):
                self.last_trigger_time = now
                self.flash_until = now + 1.8
                if self.on_detection_callback:
                    self.on_detection_callback(detected_color, qr_text)

            _, buf_raw = cv2.imencode(".jpg", raw_display, [cv2.IMWRITE_JPEG_QUALITY, 75])
            _, buf_flt = cv2.imencode(".jpg", filtered_display, [cv2.IMWRITE_JPEG_QUALITY, 75])
            with self.lock:
                self.raw_jpeg = buf_raw.tobytes()
                self.filtered_jpeg = buf_flt.tobytes()

            time.sleep(0.04)


# ==============================================================================
# LOGICA DE VALIDACION EN BANDA Y ACTIVACION DE SERVOS (ADAPTADA A trisomicos_bd)
# ==============================================================================
def registrar_lectura_banda(color_detectado: str, qr_detectado: str = "") -> Dict[str, Any]:
    if not ACTIVE_SESSION["auto_scan_enabled"]:
        return {"ok": False, "motivo": "Escaneo automatico pausado"}

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    id_lote = int(ACTIVE_SESSION["id_lote"])

    qr_codigo = None
    qr_estado = "CORRECTO"
    if qr_detectado and "|" in qr_detectado:
        parts = qr_detectado.split("|")
        qr_codigo = parts[0].strip()
        if len(parts) > 1 and parts[1].strip():
            color_detectado = parts[1].strip().upper()
        if len(parts) > 2 and parts[2].strip():
            qr_estado = parts[2].strip().upper()

    color_detectado = (color_detectado or "").strip().upper()

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Buscar color en el esquema real de MariaDB trisomicos_bd
            cur.execute(
                """
                SELECT cp.ID_COLOR_PRODUCTO, cp.ID_PRODUCTO, cp.ID_PROVEEDOR, cp.NOMBRE_COLOR,
                       p.NOMBRE_PRODUCTO, pr.NOMBRE_PROVEEDOR
                FROM color_producto cp
                JOIN producto p ON p.ID_PRODUCTO = cp.ID_PRODUCTO
                JOIN proveedor pr ON pr.ID_PROVEEDOR = cp.ID_PROVEEDOR
                WHERE UPPER(cp.NOMBRE_COLOR) = %s
                LIMIT 1
                """,
                (color_detectado,),
            )
            cp = cur.fetchone()

            if not cp:
                msg = f"[{now_str}] Lectura ignorada: color '{color_detectado}' no esta en color_producto."
                ACTIVE_SESSION["last_event"] = msg
                return {"ok": False, "motivo": msg}

            # Obtener informacion del lote activo y su OC en trisomicos_bd
            cur.execute(
                """
                SELECT lr.ID_LOTE, lr.ID_OC, lr.CANTIDAD_CAJAS_ESPERADA, lr.CANTIDAD_CAJAS_CONTADA,
                       oc.ID_PROVEEDOR AS OC_PROV, ocd.ID_PRODUCTO AS OC_PROD, ocd.PIEZAS_POR_CAJA
                FROM lote_recepcion lr
                JOIN orden_compra oc ON oc.ID_OC = lr.ID_OC
                JOIN orden_compra_detalle ocd ON ocd.ID_OC = oc.ID_OC
                WHERE lr.ID_LOTE = %s
                LIMIT 1
                """,
                (id_lote,),
            )
            lote_info = cur.fetchone()
            if not lote_info:
                msg = f"[{now_str}] Lote #{id_lote} no encontrado en lote_recepcion."
                ACTIVE_SESSION["last_event"] = msg
                return {"ok": False, "motivo": msg}

            coincide_oc = (
                cp["ID_PRODUCTO"] == lote_info["OC_PROD"]
                and cp["ID_PROVEEDOR"] == lote_info["OC_PROV"]
            )

            # Determinar estado de inspeccion y accion de servo
            if qr_estado in ("DANADO", "DAÑADO"):
                servo = "SERVO_1"
                servo_desc = "SERVO 1 (CAJA DANADA)"
                ruta = "SERVO_1_DANADA"
                resultado = "RETENIDA"
                estado_inspeccion = "DANADA"
            elif qr_estado in ("INCORRECTO", "NO_ESPERADO") or not coincide_oc:
                servo = "SERVO_2"
                servo_desc = "SERVO 2 (NO ESPERADO)"
                ruta = "SERVO_2_NO_ESPERADO"
                resultado = "RETENIDA"
                estado_inspeccion = "NO_ESPERADA"
            else:
                servo = "NINGUNO"
                servo_desc = "NINGUNO (NORMAL - PASA)"
                ruta = "NORMAL_OK"
                resultado = "OK"
                estado_inspeccion = "OK"

            codigo_final = qr_codigo or f"CJ-{now_dt.strftime('%H%M%S')}-{random.randint(10, 99)}"

            # Verificar duplicado en tabla caja (esquema MariaDB trisomicos_bd)
            cur.execute("SELECT ID_CAJA FROM caja WHERE CODIGO_CAJA = %s", (codigo_final,))
            if cur.fetchone():
                vision.servo_state = "SERVO_2"
                vision.servo_label = "SERVO 2 (DUPLICADO)"
                ACTIVE_SESSION["servo_activado"] = "SERVO 2 (DUPLICADO)"
                ACTIVE_SESSION["last_route"] = "SERVO_2_DUPLICADO"
                ACTIVE_SESSION["ultimo_comando_esp32"] = {"servo": "SERVO_2", "ruta": "SERVO_2_DUPLICADO", "timestamp": now_str}
                msg = f"[{now_str}] ALERTA DUPLICADO: {codigo_final} -> SERVO 2."
                ACTIVE_SESSION["last_event"] = msg
                return {"ok": False, "servo": "SERVO_2", "motivo": msg}

            # Insertar en tabla caja (columnas exactas de trisomicos_bd.sql)
            piezas_caja = lote_info.get("PIEZAS_POR_CAJA") or 1
            cur.execute(
                """
                INSERT INTO caja
                    (CODIGO_CAJA, ID_LOTE, ID_COLOR_PRODUCTO, ESTADO_INSPECCION,
                     CANTIDAD_REAL, RUTA_ASIGNADA, LEIDA, FECHA_LECTURA_BANDA)
                VALUES (%s, %s, %s, %s, %s, %s, 1, %s)
                """,
                (codigo_final, id_lote, cp["ID_COLOR_PRODUCTO"], estado_inspeccion, piezas_caja, ruta, now_str),
            )
            id_caja = cur.lastrowid

            # Insertar en lectura_banda (columnas exactas de trisomicos_bd.sql)
            cur.execute(
                """
                INSERT INTO lectura_banda (ID_CAJA, TIMESTAMP_LECTURA, RESULTADO)
                VALUES (%s, %s, %s)
                """,
                (id_caja, now_str, resultado),
            )

            # Actualizar conteo del lote
            nuevo_conteo = (lote_info["CANTIDAD_CAJAS_CONTADA"] or 0) + 1
            esperadas = lote_info["CANTIDAD_CAJAS_ESPERADA"] or 0
            nuevo_estado_lote = 1  # EN_RECEPCION
            if nuevo_conteo == esperadas:
                nuevo_estado_lote = 2  # COMPLETO
            elif nuevo_conteo > esperadas:
                nuevo_estado_lote = 4  # EXCEDENTE

            cur.execute(
                "UPDATE lote_recepcion SET CANTIDAD_CAJAS_CONTADA = %s, ID_ESTADO_LOTE = %s WHERE ID_LOTE = %s",
                (nuevo_conteo, nuevo_estado_lote, id_lote),
            )

            # Generar orden_trabajo automatica si hubo desviacion o excedente (esquema trisomicos_bd.sql)
            ot_id = None
            if servo != "NINGUNO":
                cur.execute(
                    """
                    INSERT INTO orden_trabajo
                        (ID_TIPO_INCIDENCIA, ID_ESTADO_ORDEN_TRABAJO, ID_LOTE, ID_CAJA, FECHA_GENERACION)
                    VALUES (1, 1, %s, %s, %s)
                    """,
                    (id_lote, id_caja, now_str),
                )
                ot_id = cur.lastrowid
            elif nuevo_conteo > esperadas:
                cur.execute(
                    """
                    INSERT INTO orden_trabajo
                        (ID_TIPO_INCIDENCIA, ID_ESTADO_ORDEN_TRABAJO, ID_LOTE, ID_CAJA, FECHA_GENERACION)
                    VALUES (4, 1, %s, %s, %s)
                    """,
                    (id_lote, id_caja, now_str),
                )
                ot_id = cur.lastrowid

        conn.commit()

    conteo_txt = f"{nuevo_conteo} / {esperadas}"
    vision.servo_state = servo
    vision.servo_label = servo_desc
    vision.lote_conteo_texto = conteo_txt

    ACTIVE_SESSION["servo_activado"] = servo_desc
    ACTIVE_SESSION["conteo_actual"] = conteo_txt
    ACTIVE_SESSION["last_route"] = ruta
    ACTIVE_SESSION["ultimo_comando_esp32"] = {
        "servo": servo,
        "ruta": ruta,
        "codigo_caja": codigo_final,
        "id_lote": id_lote,
        "timestamp": now_str,
    }
    ACTIVE_SESSION["last_event"] = (
        f"[{now_str}] CAJA #{nuevo_conteo}/{esperadas} ({codigo_final}) | {cp['NOMBRE_COLOR']} - {cp['NOMBRE_PRODUCTO']} -> {servo_desc}"
        + (f" [OT #{ot_id}]" if ot_id else "")
    )
    return {"ok": True, "servo": servo, "ruta": ruta, "codigo_caja": codigo_final, "ot_id": ot_id}


vision = VisionSystem(on_detection_callback=registrar_lectura_banda)


@app.on_event("startup")
def startup_event():
    try:
        ensure_runtime_tables_and_catalogs()
        sincronizar_conteo_lote(ACTIVE_SESSION["id_lote"])
    except Exception as exc:
        ACTIVE_SESSION["last_event"] = f"Error inicializando BD: {exc}"
    vision.start(CAMERA_INDEX)


@app.on_event("shutdown")
def shutdown_event():
    vision.stop()


# ==============================================================================
# GENERADOR DE TICKETS TERMICOS (JPG / PDF) + VALIDACION CONTRA trisomicos_bd
# ==============================================================================
def get_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def get_mono_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def draw_barcode(draw, x: int, y: int, width: int, height: int, code_str: str):
    rng = random.Random(code_str)
    cursor = x
    end_x = x + width
    for w in [4, 2, 4]:
        draw.rectangle([cursor, y, cursor + w, y + height], fill=(0, 0, 0))
        cursor += w + 3
    while cursor < end_x - 25:
        bar_w = rng.choice([2, 4, 6, 8])
        space_w = rng.choice([2, 4, 6])
        if cursor + bar_w > end_x - 20:
            break
        draw.rectangle([cursor, y, cursor + bar_w, y + height], fill=(0, 0, 0))
        cursor += bar_w + space_w
    for w in [4, 2, 4]:
        if cursor + w <= end_x:
            draw.rectangle([cursor, y, cursor + w, y + height], fill=(0, 0, 0))
            cursor += w + 3


def obtener_catalogo_desde_bd() -> List[Dict[str, Any]]:
    """Lee directamente las OCs y lotes reales de trisomicos_bd para generar tickets alineados."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT oc.ID_OC, p.NOMBRE_PROVEEDOR, pr.NOMBRE_PRODUCTO, pr.UNIDAD_MEDIDA,
                       ocd.CANTIDAD_CAJAS_ESPERADA, ocd.PIEZAS_POR_CAJA,
                       lr.ID_LOTE
                FROM orden_compra oc
                JOIN proveedor p ON oc.ID_PROVEEDOR = p.ID_PROVEEDOR
                JOIN orden_compra_detalle ocd ON oc.ID_OC = ocd.ID_OC
                JOIN producto pr ON ocd.ID_PRODUCTO = pr.ID_PRODUCTO
                LEFT JOIN lote_recepcion lr ON lr.ID_OC = oc.ID_OC
                ORDER BY oc.ID_OC
                """
            )
            rows = cur.fetchall()
    return rows


def generar_datos_ticket(indice: int, escenario_forzado: Optional[str] = None, oc_id: Optional[int] = None) -> Dict[str, Any]:
    catalogo = obtener_catalogo_desde_bd()
    if not catalogo:
        raise HTTPException(status_code=400, detail="No hay ordenes de compra registradas en trisomicos_bd.")

    item = random.choice(catalogo)
    if oc_id is not None:
        match = next((x for x in catalogo if x["ID_OC"] == oc_id), None)
        if match:
            item = match

    ordered_qty = int((item["CANTIDAD_CAJAS_ESPERADA"] or 1) * (item["PIEZAS_POR_CAJA"] or 1))
    escenarios = ["COINCIDE", "DIFIERE_PARCIAL", "DIFIERE_EXCEDENTE", "DIFIERE_NO_CUADRA_FISICO", "INCOMPLETO"]
    escenario = escenario_forzado or random.choice(escenarios)

    received_qty = ordered_qty
    measured_qty = ordered_qty
    unit_cost: Optional[float] = round(random.uniform(1.5, 145.0), 2)
    lot_id = item.get("ID_LOTE") or item["ID_OC"]
    status = "COINCIDE"
    action = "APROBAR RECEPCION Y SURTIR OT"

    if escenario == "DIFIERE_PARCIAL":
        diff = max(1, int(ordered_qty * random.uniform(0.10, 0.30)))
        received_qty = ordered_qty - diff
        measured_qty = received_qty
        status = "DIFIERE_PARCIAL"
        action = "RECLAMAR FALTANTE Y GENERAR OT"
    elif escenario == "DIFIERE_EXCEDENTE":
        diff = max(1, int(ordered_qty * random.uniform(0.10, 0.25)))
        received_qty = ordered_qty + diff
        measured_qty = received_qty
        status = "DIFIERE_EXCEDENTE"
        action = "ENVIAR EXCEDENTE A CUARENTENA"
    elif escenario == "DIFIERE_NO_CUADRA_FISICO":
        received_qty = ordered_qty
        delta_fisico = random.choice([-1, 1]) * max(1, int(ordered_qty * random.uniform(0.15, 0.35)))
        measured_qty = max(0, received_qty + delta_fisico)
        status = "DIFIERE_NO_CUADRA_FISICO"
        action = "BLOQUEAR SALDO Y DISPARAR RECONTEO"
    elif escenario == "INCOMPLETO":
        unit_cost = None
        status = "INCOMPLETO"
        action = "AISLAR REGISTRO (FALTA COSTO)"

    delta_vs_order = (measured_qty - ordered_qty) if status == "DIFIERE_NO_CUADRA_FISICO" else (received_qty - ordered_qty)
    sku_fmt = item["NOMBRE_PRODUCTO"].replace("_", "-")

    return {
        "ticket_id": f"TCK-2026-{indice:04d}",
        "oc_id": item["ID_OC"],
        "lote_id": lot_id,
        "po_id": f"OC-{item['ID_OC']:04d}",
        "supplier": item["NOMBRE_PROVEEDOR"],
        "sku": sku_fmt,
        "desc": f"{item['NOMBRE_PRODUCTO']} ({item['CANTIDAD_CAJAS_ESPERADA']} cajas x {item['PIEZAS_POR_CAJA']})",
        "zone": f"RACK-0{item['ID_OC']}",
        "unit": (item["UNIDAD_MEDIDA"] or "PZA").lower(),
        "ordered_qty": ordered_qty,
        "received_qty": received_qty,
        "measured_qty": measured_qty,
        "delta_vs_order": delta_vs_order,
        "unit_cost_mxn": unit_cost,
        "lot": f"LOTE-{lot_id:03d}",
        "status": status,
        "recommended_action": action,
        "linked_wo": f"OT-LOTE-{lot_id}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def render_ticket_image(ticket: Dict[str, Any]) -> Image.Image:
    W, H = 812, 1218
    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    f_title = get_font(34, bold=True)
    f_sub = get_font(20, bold=True)
    f_lbl = get_font(17, bold=True)
    f_val = get_font(21, bold=False)
    f_val_b = get_font(22, bold=True)
    f_big = get_font(44, bold=True)
    f_mono = get_mono_font(20, bold=True)
    f_status = get_font(27, bold=True)

    m = 24
    draw.rectangle([m, m, W - m, H - m], outline=(0, 0, 0), width=5)
    draw.rectangle([m, m, W - m, m + 95], fill=(15, 23, 42))
    draw.text((m + 20, m + 16), "ETIQUETA DE RECEPCION / ALMACEN", fill=(255, 255, 255), font=f_title)
    draw.text((m + 20, m + 58), f"TRISOMICOS_BD & IOT  |  {ticket['timestamp']}", fill=(203, 213, 225), font=f_lbl)

    y = m + 95
    mid_x = W // 2 + 40
    draw.line([m, y + 125, W - m, y + 125], fill=(0, 0, 0), width=3)
    draw.line([mid_x, y, mid_x, y + 125], fill=(0, 0, 0), width=3)

    draw.text((m + 18, y + 12), "PROVEEDOR / ORIGEN:", fill=(71, 85, 105), font=f_lbl)
    draw.text((m + 18, y + 40), ticket["supplier"], fill=(0, 0, 0), font=f_val_b)
    draw.text((m + 18, y + 76), f"{ticket['po_id']}   |   {ticket['lot']}", fill=(0, 0, 0), font=f_val)

    draw.text((mid_x + 18, y + 12), "DESTINO / ZONA:", fill=(71, 85, 105), font=f_lbl)
    draw.text((mid_x + 18, y + 42), ticket["zone"], fill=(0, 0, 0), font=f_big)

    y += 125
    draw.line([m, y + 135, W - m, y + 135], fill=(0, 0, 0), width=3)
    draw.text((m + 18, y + 12), "MATERIAL / SKU:", fill=(71, 85, 105), font=f_lbl)
    draw.text((m + 18, y + 38), ticket["sku"], fill=(0, 0, 0), font=f_big)
    draw.text((m + 18, y + 92), f"{ticket['desc']}   |   {ticket['linked_wo']}", fill=(0, 0, 0), font=f_val)

    y += 135
    draw.line([m, y + 175, W - m, y + 175], fill=(0, 0, 0), width=4)
    col_w = (W - 2 * m) // 4
    headers = ["PEDIDO (OC)", "RECIBIDO (DOC)", "SENSOR (IOT)", "DIFERENCIA"]
    vals = [
        f"{ticket['ordered_qty']} {ticket['unit']}",
        f"{ticket['received_qty']} {ticket['unit']}",
        f"{ticket['measured_qty']} {ticket['unit']}",
        f"{ticket['delta_vs_order']:+d} {ticket['unit']}",
    ]
    for idx in range(4):
        cx = m + idx * col_w
        if idx > 0:
            draw.line([cx, y, cx, y + 175], fill=(0, 0, 0), width=2)
        draw.rectangle([cx + 2, y + 2, cx + col_w - 2, y + 42], fill=(241, 245, 249))
        draw.text((cx + 12, y + 11), headers[idx], fill=(30, 41, 59), font=f_lbl)
        draw.text((cx + 14, y + 72), vals[idx], fill=(0, 0, 0), font=f_title)

    y += 175
    draw.line([m, y + 75, W - m, y + 75], fill=(0, 0, 0), width=3)
    draw.line([mid_x, y, mid_x, y + 75], fill=(0, 0, 0), width=2)
    costo_txt = f"${ticket['unit_cost_mxn']:.2f} MXN" if ticket["unit_cost_mxn"] is not None else "FALTANTE (NULL)"
    draw.text((m + 18, y + 25), f"COSTO UNIT.: {costo_txt}", fill=(0, 0, 0), font=f_val_b)
    draw.text((mid_x + 18, y + 25), f"FOLIO: {ticket['ticket_id']}", fill=(0, 0, 0), font=f_val_b)

    y += 75
    es_ok = ticket["status"] == "COINCIDE"
    banner_color = (22, 101, 52) if es_ok else (153, 27, 27)
    draw.rectangle([m + 14, y + 18, W - m - 14, y + 135], fill=banner_color)
    draw.text((m + 30, y + 30), f"DICTAMEN: {ticket['status']}", fill=(255, 255, 255), font=f_status)
    draw.text((m + 30, y + 78), f"ACCION: {ticket['recommended_action']}", fill=(255, 255, 255), font=f_sub)

    y += 155
    draw.line([m, y, W - m, y], fill=(0, 0, 0), width=3)
    barcode_val = f"{ticket['ticket_id']}-{ticket['po_id']}-{ticket['sku']}"
    draw_barcode(draw, m + 55, y + 30, W - 2 * m - 110, 175, barcode_val)
    bbox = draw.textbbox((0, 0), barcode_val, font=f_mono)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y + 220), barcode_val, fill=(0, 0, 0), font=f_mono)

    footer_txt = "SISTEMA INTELIGENTE DE ALMACEN  |  ZERO 2W + TRISOMICOS_BD"
    fbbox = draw.textbbox((0, 0), footer_txt, font=f_lbl)
    fw = fbbox[2] - fbbox[0]
    draw.text(((W - fw) // 2, H - m - 42), footer_txt, fill=(71, 85, 105), font=f_lbl)
    return img


def validar_ticket_en_bd(ticket: Dict[str, Any], crear_ot: bool = True) -> Dict[str, Any]:
    sku_norm = norm_sku(ticket.get("sku"))
    oc_id = int(ticket.get("oc_id") or 1)
    lote_id = int(ticket.get("lote_id") or 1)

    observaciones: List[str] = []
    coincide_bd = True

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT oc.ID_OC, oc.ID_PROVEEDOR, p.NOMBRE_PROVEEDOR,
                       ocd.ID_PRODUCTO, pr.NOMBRE_PRODUCTO, pr.UNIDAD_MEDIDA,
                       ocd.CANTIDAD_CAJAS_ESPERADA AS OC_CAJAS,
                       ocd.PIEZAS_POR_CAJA
                FROM orden_compra oc
                JOIN proveedor p ON oc.ID_PROVEEDOR = p.ID_PROVEEDOR
                JOIN orden_compra_detalle ocd ON oc.ID_OC = ocd.ID_OC
                JOIN producto pr ON ocd.ID_PRODUCTO = pr.ID_PRODUCTO
                WHERE oc.ID_OC = %s
                LIMIT 1
                """,
                (oc_id,),
            )
            oc_row = cur.fetchone()

            cur.execute(
                """
                SELECT lr.ID_LOTE, lr.ID_OC, lr.CANTIDAD_CAJAS_ESPERADA AS LOTE_CAJAS_ESP,
                       lr.CANTIDAD_CAJAS_CONTADA AS LOTE_CAJAS_CONT,
                       el.NOMBRE_ESTADO_LOTE
                FROM lote_recepcion lr
                JOIN estado_lote el ON lr.ID_ESTADO_LOTE = el.ID_ESTADO_LOTE
                WHERE lr.ID_LOTE = %s
                LIMIT 1
                """,
                (lote_id,),
            )
            lote_row = cur.fetchone()

            if not oc_row:
                coincide_bd = False
                observaciones.append(f"OC {oc_id} no encontrada en orden_compra.")
            else:
                bd_sku = norm_sku(oc_row["NOMBRE_PRODUCTO"])
                if bd_sku != sku_norm:
                    coincide_bd = False
                    observaciones.append(f"SKU del ticket ({sku_norm}) difiere del producto en OC {oc_id} ({bd_sku}).")

                unidades_esperadas_bd = (oc_row["OC_CAJAS"] or 0) * (oc_row["PIEZAS_POR_CAJA"] or 1)
                if int(ticket.get("ordered_qty") or 0) != int(unidades_esperadas_bd):
                    coincide_bd = False
                    observaciones.append(
                        f"Cantidad pedida ({ticket.get('ordered_qty')}) difiere de OC ({oc_row['OC_CAJAS']} cajas x {oc_row['PIEZAS_POR_CAJA']} = {unidades_esperadas_bd})."
                    )

            if ticket.get("status") != "COINCIDE":
                coincide_bd = False
                observaciones.append(f"Dictamen de ticket: {ticket.get('status')} ({ticket.get('recommended_action')}).")

            if ticket.get("unit_cost_mxn") is None:
                coincide_bd = False
                observaciones.append("Falta costo unitario (unit_cost_mxn es NULL).")

            # Guardar ticket en historico tickets_simulados
            cur.execute(
                """
                INSERT IGNORE INTO tickets_simulados
                (TICKET_ID, ID_OC, ID_LOTE, PO_ID, SUPPLIER, SKU, UNIT, ORDERED_QTY, RECEIVED_QTY, MEASURED_QTY,
                 DELTA_VS_ORDER, UNIT_COST_MXN, LOT, SCENARIO, STATUS, RECOMMENDED_ACTION, LINKED_WO, CREATED_AT)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    ticket["ticket_id"], oc_id, lote_id, ticket["po_id"], ticket["supplier"], ticket["sku"],
                    ticket["unit"], ticket["ordered_qty"], ticket["received_qty"], ticket["measured_qty"],
                    ticket["delta_vs_order"], ticket["unit_cost_mxn"], ticket["lot"], ticket["status"],
                    ticket["status"], ticket["recommended_action"], ticket["linked_wo"],
                ),
            )

            ot_generada_id = None
            if crear_ot and not coincide_bd and lote_row:
                tipo_inc = 1  # REVISION_CAJA_RETENIDA
                if ticket.get("status") == "DIFIERE_PARCIAL" or (ticket.get("delta_vs_order") or 0) < 0:
                    tipo_inc = 3  # LOTE_INCOMPLETO
                elif ticket.get("status") == "DIFIERE_EXCEDENTE" or (ticket.get("delta_vs_order") or 0) > 0:
                    tipo_inc = 4  # LOTE_EXCEDENTE

                cur.execute(
                    """
                    INSERT INTO orden_trabajo
                        (ID_TIPO_INCIDENCIA, ID_ESTADO_ORDEN_TRABAJO, ID_LOTE, ID_CAJA, FECHA_GENERACION)
                    VALUES (%s, 1, %s, NULL, NOW())
                    """,
                    (tipo_inc, lote_row["ID_LOTE"]),
                )
                ot_generada_id = cur.lastrowid

        conn.commit()

    return {
        "validacion_bd": "COINCIDE_CON_BD" if coincide_bd else "DIFIERE_O_REQUIERE_REVISION",
        "coincide_bd": coincide_bd,
        "observaciones": observaciones if observaciones else ["Todos los campos coinciden con trisomicos_bd."],
        "oc_bd": oc_row,
        "lote_bd": lote_row,
        "ot_generada_id": ot_generada_id,
    }


# ==============================================================================
# MODELOS Y ENDPOINTS FASTAPI (UNIFICADOS: WINDOWS + ZERO 2W + IOT ESP32/PI4)
# ==============================================================================
class ConfigVisionIn(BaseModel):
    id_lote: Optional[int] = None
    color_filter: Optional[str] = None
    auto_scan: Optional[bool] = None


class InspeccionCajaIn(BaseModel):
    id_lote: int
    id_color_producto: int
    estado_inspeccion: str
    cantidad_real: int = 1


class GenerarTicketsIn(BaseModel):
    cantidad: int = 2
    formato: str = "jpg_y_pdf"
    escenario: Optional[str] = None
    oc_id: Optional[int] = None
    validar_bd: bool = True
    crear_ot_en_falla: bool = True


class LecturaSensorIn(BaseModel):
    source_node: str
    id_caja: Optional[int] = None
    color: Optional[str] = None
    qr: Optional[str] = ""
    resultado: str = "OK"


class ComandoPi4In(BaseModel):
    command: str
    id_oc: Optional[int] = None
    id_lote: Optional[int] = None


def gen_mjpeg(stream_type: str):
    while True:
        with vision.lock:
            frame = vision.raw_jpeg if stream_type == "raw" else vision.filtered_jpeg
        if frame:
            yield (b"--frame
Content-Type: image/jpeg

" + frame + b"
")
        time.sleep(0.05)


@app.get("/video/raw")
def video_raw():
    return StreamingResponse(gen_mjpeg("raw"), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/video/filtered")
def video_filtered():
    return StreamingResponse(gen_mjpeg("filtered"), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/dashboard")
def get_dashboard():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT lr.ID_LOTE, lr.ID_OC, pr.NOMBRE_PROVEEDOR, p.NOMBRE_PRODUCTO,
                       cp.NOMBRE_COLOR, cp.ID_COLOR_PRODUCTO,
                       ocd.CANTIDAD_CAJAS_ESPERADA AS OC_CAJAS, ocd.PIEZAS_POR_CAJA,
                       lr.CANTIDAD_CAJAS_ESPERADA, lr.CANTIDAD_CAJAS_CONTADA, el.NOMBRE_ESTADO_LOTE
                FROM lote_recepcion lr
                JOIN orden_compra oc ON oc.ID_OC = lr.ID_OC
                JOIN proveedor pr ON pr.ID_PROVEEDOR = oc.ID_PROVEEDOR
                JOIN orden_compra_detalle ocd ON ocd.ID_OC = oc.ID_OC
                JOIN producto p ON p.ID_PRODUCTO = ocd.ID_PRODUCTO
                JOIN estado_lote el ON el.ID_ESTADO_LOTE = lr.ID_ESTADO_LOTE
                LEFT JOIN color_producto cp ON cp.ID_PRODUCTO = p.ID_PRODUCTO AND cp.ID_PROVEEDOR = pr.ID_PROVEEDOR
                ORDER BY lr.ID_LOTE ASC
                """
            )
            lotes = cur.fetchall()
            for l in lotes:
                col_name = (l.get("NOMBRE_COLOR") or "AZUL").upper()
                l["CODIGO_HEX"] = COLOR_RANGES_HSV.get(col_name, {"hex": "#38bdf8"})["hex"]

            cur.execute(
                """
                SELECT cp.ID_COLOR_PRODUCTO, cp.ID_PRODUCTO, cp.ID_PROVEEDOR, cp.NOMBRE_COLOR,
                       p.NOMBRE_PRODUCTO, pr.NOMBRE_PROVEEDOR
                FROM color_producto cp
                JOIN producto p ON p.ID_PRODUCTO = cp.ID_PRODUCTO
                JOIN proveedor pr ON pr.ID_PROVEEDOR = cp.ID_PROVEEDOR
                ORDER BY cp.ID_COLOR_PRODUCTO ASC
                """
            )
            colores = cur.fetchall()

            cur.execute(
                """
                SELECT lb.ID_LECTURA, c.CODIGO_CAJA, c.ID_LOTE, cp.NOMBRE_COLOR AS COLOR_DETECTADO,
                       c.ESTADO_INSPECCION, c.RUTA_ASIGNADA AS RUTA_ACCIONADA,
                       lb.RESULTADO, lb.TIMESTAMP_LECTURA
                FROM lectura_banda lb
                JOIN caja c ON c.ID_CAJA = lb.ID_CAJA
                JOIN color_producto cp ON cp.ID_COLOR_PRODUCTO = c.ID_COLOR_PRODUCTO
                ORDER BY lb.ID_LECTURA DESC LIMIT 15
                """
            )
            lecturas = cur.fetchall()

            cur.execute(
                """
                SELECT ot.ID_ORDEN_TRABAJO AS ID_OT, ot.ID_LOTE, ot.ID_CAJA,
                       ti.NOMBRE_TIPO_INCIDENCIA, eot.NOMBRE_ESTADO_ORDEN_TRABAJO,
                       ot.FECHA_GENERACION AS FECHA_CREACION
                FROM orden_trabajo ot
                JOIN tipo_incidencia ti ON ti.ID_TIPO_INCIDENCIA = ot.ID_TIPO_INCIDENCIA
                JOIN estado_orden_trabajo eot ON eot.ID_ESTADO_ORDEN_TRABAJO = ot.ID_ESTADO_ORDEN_TRABAJO
                ORDER BY ot.ID_ORDEN_TRABAJO DESC LIMIT 15
                """
            )
            ordenes_trabajo = cur.fetchall()

            cur.execute("SELECT * FROM tickets_simulados ORDER BY ID_TICKET DESC LIMIT 15")
            tickets = cur.fetchall()

    for r in lecturas:
        if r.get("TIMESTAMP_LECTURA"):
            r["TIMESTAMP_LECTURA"] = str(r["TIMESTAMP_LECTURA"])
    for r in ordenes_trabajo:
        if r.get("FECHA_CREACION"):
            r["FECHA_CREACION"] = str(r["FECHA_CREACION"])
    for r in tickets:
        if r.get("CREATED_AT"):
            r["CREATED_AT"] = str(r["CREATED_AT"])
        if r.get("UNIT_COST_MXN") is not None:
            r["UNIT_COST_MXN"] = float(r["UNIT_COST_MXN"])

    return {
        "session": ACTIVE_SESSION,
        "vision_live": {
            "detected_color": vision.current_color,
            "detected_qr": vision.current_qr,
            "filter": vision.active_color_filter,
            "camera_online": vision.camera_online,
        },
        "lotes": lotes,
        "colores": colores,
        "lecturas": lecturas,
        "ordenes_trabajo": ordenes_trabajo,
        "tickets": tickets,
    }


@app.post("/api/config")
def update_config(cfg: ConfigVisionIn):
    if cfg.id_lote is not None:
        ACTIVE_SESSION["id_lote"] = cfg.id_lote
        sincronizar_conteo_lote(cfg.id_lote)
    if cfg.color_filter is not None:
        vision.active_color_filter = cfg.color_filter
    if cfg.auto_scan is not None:
        ACTIVE_SESSION["auto_scan_enabled"] = cfg.auto_scan
    return {"ok": True, "session": ACTIVE_SESSION, "filter": vision.active_color_filter}


@app.post("/api/etiqueta/generar")
def crear_etiqueta_qr(data: InspeccionCajaIn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cp.*, p.NOMBRE_PRODUCTO, pr.NOMBRE_PROVEEDOR
                FROM color_producto cp
                JOIN producto p ON p.ID_PRODUCTO = cp.ID_PRODUCTO
                JOIN proveedor pr ON pr.ID_PROVEEDOR = cp.ID_PROVEEDOR
                WHERE cp.ID_COLOR_PRODUCTO = %s
                """,
                (data.id_color_producto,),
            )
            cp = cur.fetchone()

    if not cp:
        raise HTTPException(status_code=404, detail="Color/Producto no encontrado en trisomicos_bd")

    codigo_caja = f"CJ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    est = data.estado_inspeccion.upper()
    if est == "DANADO":
        ruta = "SERVO_1_DANADA"
    elif est == "INCORRECTO":
        ruta = "SERVO_2_NO_ESPERADO"
    else:
        ruta = "NINGUNO (NORMAL)"

    qr_payload = f"{codigo_caja}|{cp['NOMBRE_COLOR']}|{est}"
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    col_hex = COLOR_RANGES_HSV.get(cp["NOMBRE_COLOR"].upper(), {"hex": "#38bdf8"})["hex"]

    return {
        "codigo_caja": codigo_caja,
        "qr_payload": qr_payload,
        "qr_base64": qr_b64,
        "color": cp["NOMBRE_COLOR"],
        "hex": col_hex,
        "producto": cp["NOMBRE_PRODUCTO"],
        "proveedor": cp["NOMBRE_PROVEEDOR"],
        "estado": est,
        "cantidad_real": data.cantidad_real,
        "ruta": ruta,
    }


@app.post("/api/tickets/generar")
def api_generar_tickets(req: GenerarTicketsIn):
    cant = max(1, min(req.cantidad, 20))
    tickets_data = []
    imgs = []

    base_num = len(os.listdir(OUTPUT_DIR)) + 1
    for i in range(cant):
        t = generar_datos_ticket(base_num + i, escenario_forzado=req.escenario, oc_id=req.oc_id)
        img = render_ticket_image(t)
        imgs.append(img)

        jpg_name = f"{t['ticket_id']}_{t['status']}.jpg"
        if req.formato in ("jpg", "jpg_y_pdf"):
            img.save(os.path.join(OUTPUT_DIR, jpg_name), "JPEG", quality=90)
            t["jpg_url"] = f"/api/tickets/archivo/{jpg_name}"
        else:
            t["jpg_url"] = None

        if req.validar_bd:
            t["validacion"] = validar_ticket_en_bd(t, crear_ot=req.crear_ot_en_falla)

        tickets_data.append(t)

    pdf_url = None
    if req.formato in ("pdf", "jpg_y_pdf") and imgs:
        pdf_name = f"lote_tickets_{datetime.now().strftime('%H%M%S')}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, pdf_name)
        imgs[0].save(pdf_path, "PDF", resolution=203.0, save_all=True, append_images=imgs[1:])
        pdf_url = f"/api/tickets/archivo/{pdf_name}"

    return {"tickets": tickets_data, "pdf_url": pdf_url}


@app.get("/api/tickets/archivo/{filename}")
def descargar_archivo(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path, filename=safe_name)


@app.post("/api/simular_paso_banda")
def simular_paso_banda(color: str, qr: str = ""):
    vision.last_trigger_time = 0
    vision.flash_until = time.time() + 1.8
    res = registrar_lectura_banda(color, qr)
    return {"ok": res.get("ok", False), "resultado": res, "session": ACTIVE_SESSION}


@app.post("/api/reset_demo")
def reset_demo():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM lectura_banda")
            cur.execute("DELETE FROM orden_trabajo")
            cur.execute("DELETE FROM caja")
            cur.execute("DELETE FROM tickets_simulados")
            cur.execute("UPDATE lote_recepcion SET CANTIDAD_CAJAS_CONTADA = 0, ID_ESTADO_LOTE = 1")
        conn.commit()
    vision.servo_state = "NINGUNO"
    vision.servo_label = "REPOSO (PASA NORMAL)"
    sincronizar_conteo_lote(ACTIVE_SESSION["id_lote"])
    ACTIVE_SESSION["last_event"] = "Base operativa reiniciada en trisomicos_bd."
    ACTIVE_SESSION["last_route"] = "STANDBY"
    ACTIVE_SESSION["servo_activado"] = "NINGUNO (NORMAL)"
    return {"ok": True}


# ==============================================================================
# ENDPOINTS IOT PARA ORANGE PI 4 PRO Y ESP32 (SERVO 1 / SERVO 2 / SENSORES)
# ==============================================================================
@app.post("/api/v1/sensor")
def api_sensor_esp32(ev: LecturaSensorIn):
    if ev.color:
        res = registrar_lectura_banda(ev.color, ev.qr or "")
        return {"ok": True, "source_node": ev.source_node, "accion_servo": ACTIVE_SESSION["ultimo_comando_esp32"], "detalle": res}
    if ev.id_caja:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO lectura_banda (ID_CAJA, TIMESTAMP_LECTURA, RESULTADO) VALUES (%s, NOW(), %s)",
                    (ev.id_caja, ev.resultado[:10]),
                )
            conn.commit()
    return {"ok": True, "source_node": ev.source_node, "accion_servo": ACTIVE_SESSION["ultimo_comando_esp32"]}


@app.get("/api/v1/servo/ultimo")
def api_estado_servo_esp32():
    """El ESP32 puede consultar este endpoint para accionar Servo 1 (danada) o Servo 2 (no esperada)."""
    return ACTIVE_SESSION["ultimo_comando_esp32"]


@app.post("/api/v1/commands")
def api_comando_pi4(cmd: ComandoPi4In):
    if cmd.command == "CONSULTAR_OC" and cmd.id_oc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM orden_compra_detalle WHERE ID_OC = %s", (cmd.id_oc,))
                rows = cur.fetchall()
        return {"ok": True, "command": cmd.command, "detalle_oc": rows}
    if cmd.command == "SELECCIONAR_LOTE" and cmd.id_lote:
        ACTIVE_SESSION["id_lote"] = cmd.id_lote
        sincronizar_conteo_lote(cmd.id_lote)
        return {"ok": True, "session": ACTIVE_SESSION}
    return {"ok": True, "command": cmd.command}


# ==============================================================================
# INTERFAZ WEB UNIFICADA (VISION HSV + SERVOS + QR + TICKETS JPG/PDF + BD)
# ==============================================================================
HTML_UI = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CEDIS IoT Zero 2W — Visión HSV, Servos, Tickets y trisomicos_bd</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; background: #0b1120; color: #e2e8f0; margin: 0; padding: 14px; }
    h1, h2, h3 { margin: 0 0 10px 0; color: #38bdf8; }
    .topbar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: space-between; align-items: center; background: #1e293b; padding: 12px 16px; border-radius: 10px; margin-bottom: 12px; border: 1px solid #334155; }
    .badge { padding: 5px 11px; border-radius: 999px; font-weight: 700; font-size: 12px; background: #0284c7; color: #fff; display: inline-block; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
    @media (max-width: 960px) { .grid-2 { grid-template-columns: 1fr; } }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 14px; }
    .video-box { width: 100%; border-radius: 8px; border: 2px solid #334155; background: #000; display: block; }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
    select, input, button { background: #0f172a; color: #f8fafc; border: 1px solid #475569; padding: 7px 11px; border-radius: 6px; font-size: 13px; }
    button { background: #2563eb; border: none; font-weight: 600; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    button.warn { background: #dc2626; }
    button.ok { background: #16a34a; }
    table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }
    th, td { border-bottom: 1px solid #334155; padding: 6px 8px; text-align: left; }
    th { color: #94a3b8; background: #0f172a; }
    .status-bar { background: #0f172a; border-left: 4px solid #22c55e; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 10px; justify-content: space-between; align-items: center; font-size: 13px; }
    .qr-preview { display: flex; gap: 14px; align-items: center; margin-top: 10px; background: #0f172a; padding: 10px; border-radius: 8px; }
    .ticket-item { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px; margin-top: 10px; font-size: 13px; }
    .txt-ok { color: #4ade80; font-weight: 700; }
    .txt-err { color: #f87171; font-weight: 700; }
    a { color: #7dd3fc; }
  </style>
</head>
<body>
  <div class="topbar">
    <div>
      <h1 style="font-size:19px;">CEDIS IoT Zero 2W — Visión HSV, Servos, Tickets y <code>trisomicos_bd</code></h1>
      <small style="color:#94a3b8;">Servo 1: Dañada | Servo 2: No Esperado / Duplicado | MariaDB en vivo</small>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap;">
      <span class="badge" id="badge-cam" style="background:#334155;">CAM: VERIFICANDO</span>
      <span class="badge" id="badge-conteo">CONTEO: 0 / 0</span>
      <span class="badge" style="background:#7c3aed;" id="badge-servo">SERVO: NINGUNO</span>
    </div>
  </div>

  <div class="status-bar">
    <div id="last-event">Cargando estado de trisomicos_bd...</div>
    <div>
      <button onclick="refreshDashboard()">Actualizar</button>
      <button class="warn" onclick="resetDemo()">Reiniciar Demo</button>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>Streaming Cámara Real (Color HSV + QR)</h3>
      <img class="video-box" src="/video/raw" />
      <div class="controls">
        <label>Lote activo:</label>
        <select id="sel-lote" onchange="updateConfig()"></select>
        <button class="ok" onclick="simularPaso('AZUL')">Simular AZUL (Normal)</button>
        <button class="warn" onclick="simularPaso('AZUL', 'CJ-TEST|AZUL|DANADO')">Simular Dañada (Servo 1)</button>
        <button style="background:#ea580c;" onclick="simularPaso('VERDE')">Simular No Esperado (Servo 2)</button>
      </div>
    </div>

    <div class="card">
      <h3>Filtro HSV + Cuadrículas Rojas de Disparo y Servos</h3>
      <img class="video-box" src="/video/filtered" />
      <div class="controls">
        <label>Aislar color HSV:</label>
        <select id="sel-filter" onchange="updateConfig()">
          <option value="TODOS">TODOS LOS COLORES</option>
          <option value="AZUL">AZUL</option>
          <option value="NARANJA">NARANJA</option>
          <option value="VERDE">VERDE</option>
          <option value="AMARILLO">AMARILLO</option>
          <option value="MORADO">MORADO</option>
        </select>
        <span style="font-size:12px; color:#94a3b8;">Color en zona: <b id="live-color" style="color:#38bdf8;">NINGUNO</b></span>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>Muelle — Etiqueta QR de Caja (Para Cámara o Impresión)</h3>
      <div class="controls">
        <select id="ins-color"></select>
        <select id="ins-estado">
          <option value="CORRECTO">CORRECTO (Pasa Normal)</option>
          <option value="DANADO">DAÑADO (Activa Servo 1)</option>
          <option value="INCORRECTO">INCORRECTO (Activa Servo 2)</option>
        </select>
        <input type="number" id="ins-cant" value="1" min="1" style="width:60px;" />
        <button onclick="generarEtiqueta()">Generar QR</button>
      </div>
      <div class="qr-preview" id="qr-box" style="display:none;">
        <img id="qr-img" width="110" height="110" style="background:#fff; padding:4px; border-radius:6px;" />
        <div id="qr-info" style="font-size:13px; line-height:1.5;"></div>
      </div>

      <h3 style="margin-top:16px;">Lotes en Recepción (<code>lote_recepcion</code>)</h3>
      <table>
        <thead><tr><th>Lote</th><th>Proveedor</th><th>Producto</th><th>Color</th><th>Conteo</th><th>Estado</th></tr></thead>
        <tbody id="tbl-lotes"></tbody>
      </table>
    </div>

    <div class="card">
      <h3>Generador de Tickets Térmicos (JPG / PDF) + Validación BD</h3>
      <div class="controls">
        <input id="tck-cant" type="number" min="1" max="10" value="2" style="width:55px;" title="Cantidad" />
        <select id="tck-formato">
          <option value="jpg_y_pdf">JPG + PDF</option>
          <option value="jpg">Solo JPG</option>
          <option value="pdf">Solo PDF</option>
        </select>
        <select id="tck-escenario">
          <option value="">Escenario Aleatorio</option>
          <option value="COINCIDE">COINCIDE</option>
          <option value="DIFIERE_PARCIAL">DIFIERE_PARCIAL</option>
          <option value="DIFIERE_EXCEDENTE">DIFIERE_EXCEDENTE</option>
          <option value="DIFIERE_NO_CUADRA_FISICO">NO_CUADRA_FISICO</option>
          <option value="INCOMPLETO">INCOMPLETO</option>
        </select>
        <select id="tck-oc">
          <option value="">OC Aleatoria</option>
          <option value="1">OC-0001</option>
          <option value="2">OC-0002</option>
          <option value="3">OC-0003</option>
          <option value="4">OC-0004</option>
          <option value="5">OC-0005</option>
        </select>
        <label style="font-size:12px;"><input id="tck-ot" type="checkbox" checked /> Crear OT si difiere</label>
        <button onclick="generarTickets()">Generar Tickets</button>
      </div>
      <div id="tck-pdf-link" style="margin-top:8px; font-size:13px;"></div>
      <div id="tck-resultados"></div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>Lecturas en Banda (<code>lectura_banda</code> + <code>caja</code>)</h3>
      <table>
        <thead><tr><th>Caja</th><th>Color</th><th>Inspección</th><th>Ruta / Servo</th><th>Hora</th></tr></thead>
        <tbody id="tbl-lecturas"></tbody>
      </table>
    </div>

    <div class="card">
      <h3>Órdenes de Trabajo Automáticas (<code>orden_trabajo</code>)</h3>
      <table>
        <thead><tr><th>ID OT</th><th>Lote</th><th>Caja</th><th>Tipo Incidencia</th><th>Estado</th></tr></thead>
        <tbody id="tbl-ot"></tbody>
      </table>
    </div>
  </div>

  <script>
    let initializedSelects = false;

    async function refreshDashboard() {
      try {
        const res = await fetch('/api/dashboard');
        if (!res.ok) {
          const txt = await res.text();
          document.getElementById('last-event').innerHTML = `<span class="txt-err">Error HTTP ${res.status}: ${txt}</span>`;
          return;
        }
        const data = await res.json();

        document.getElementById('last-event').textContent = data.session.last_event;
        document.getElementById('badge-conteo').textContent = 'CONTEO: ' + data.session.conteo_actual;
        document.getElementById('badge-servo').textContent = 'SERVO: ' + data.session.servo_activado;
        document.getElementById('live-color').textContent = data.vision_live.detected_color;
        const badgeCam = document.getElementById('badge-cam');
        badgeCam.textContent = data.vision_live.camera_online ? 'CAM: ACTIVA' : 'CAM: MODO SIM';
        badgeCam.style.background = data.vision_live.camera_online ? '#16a34a' : '#475569';

        if (!initializedSelects && data.lotes.length > 0) {
          const selLote = document.getElementById('sel-lote');
          selLote.innerHTML = data.lotes.map(l => `<option value="${l.ID_LOTE}">Lote #${l.ID_LOTE} (OC #${l.ID_OC} - ${l.NOMBRE_PRODUCTO} / ${l.NOMBRE_COLOR || 'SIN COLOR'})</option>`).join('');
          const selColor = document.getElementById('ins-color');
          selColor.innerHTML = data.colores.map(c => `<option value="${c.ID_COLOR_PRODUCTO}">${c.NOMBRE_COLOR} — ${c.NOMBRE_PRODUCTO}</option>`).join('');
          initializedSelects = true;
        }

        document.getElementById('tbl-lotes').innerHTML = data.lotes.length
          ? data.lotes.map(l => `<tr><td>#${l.ID_LOTE}</td><td>${l.NOMBRE_PROVEEDOR}</td><td>${l.NOMBRE_PRODUCTO}</td><td><span style="color:${l.CODIGO_HEX};font-weight:bold;">${l.NOMBRE_COLOR || '-'}</span></td><td><b>${l.CANTIDAD_CAJAS_CONTADA} / ${l.CANTIDAD_CAJAS_ESPERADA}</b></td><td>${l.NOMBRE_ESTADO_LOTE}</td></tr>`).join('')
          : '<tr><td colspan="6">Sin lotes registrados</td></tr>';

        document.getElementById('tbl-lecturas').innerHTML = data.lecturas.length
          ? data.lecturas.map(r => `<tr><td>${r.CODIGO_CAJA}</td><td>${r.COLOR_DETECTADO}</td><td>${r.ESTADO_INSPECCION}</td><td><b>${r.RUTA_ACCIONADA}</b></td><td>${(r.TIMESTAMP_LECTURA || '').split(' ')[1] || r.TIMESTAMP_LECTURA}</td></tr>`).join('')
          : '<tr><td colspan="5">Sin lecturas en banda aún</td></tr>';

        document.getElementById('tbl-ot').innerHTML = data.ordenes_trabajo.length
          ? data.ordenes_trabajo.map(o => `<tr><td>#${o.ID_OT}</td><td>Lote ${o.ID_LOTE}</td><td>${o.ID_CAJA || '-'}</td><td>${o.NOMBRE_TIPO_INCIDENCIA}</td><td>${o.NOMBRE_ESTADO_ORDEN_TRABAJO}</td></tr>`).join('')
          : '<tr><td colspan="5">Sin incidencias registradas</td></tr>';
      } catch (e) {
        document.getElementById('last-event').innerHTML = `<span class="txt-err">Error de red: ${e}</span>`;
      }
    }

    async function updateConfig() {
      await fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          id_lote: parseInt(document.getElementById('sel-lote').value, 10),
          color_filter: document.getElementById('sel-filter').value
        })
      });
      refreshDashboard();
    }

    async function generarEtiqueta() {
      const res = await fetch('/api/etiqueta/generar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          id_lote: parseInt(document.getElementById('sel-lote').value, 10),
          id_color_producto: parseInt(document.getElementById('ins-color').value, 10),
          estado_inspeccion: document.getElementById('ins-estado').value,
          cantidad_real: parseInt(document.getElementById('ins-cant').value, 10)
        })
      });
      const d = await res.json();
      document.getElementById('qr-box').style.display = 'flex';
      document.getElementById('qr-img').src = 'data:image/png;base64,' + d.qr_base64;
      document.getElementById('qr-info').innerHTML = `<b>Código:</b> ${d.codigo_caja}<br><b>Producto:</b> ${d.producto} (${d.color})<br><b>Estado:</b> ${d.estado}<br><b>Acción Servo:</b> ${d.ruta}`;
    }

    async function generarTickets() {
      const payload = {
        cantidad: parseInt(document.getElementById('tck-cant').value || '1', 10),
        formato: document.getElementById('tck-formato').value,
        escenario: document.getElementById('tck-escenario').value || null,
        oc_id: document.getElementById('tck-oc').value ? parseInt(document.getElementById('tck-oc').value, 10) : null,
        validar_bd: true,
        crear_ot_en_falla: document.getElementById('tck-ot').checked
      };
      const res = await fetch('/api/tickets/generar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      document.getElementById('tck-pdf-link').innerHTML = data.pdf_url
        ? `PDF generado: <a href="${data.pdf_url}" target="_blank">Descargar lote PDF</a>` : '';
      const cont = document.getElementById('tck-resultados');
      cont.innerHTML = (data.tickets || []).map(t => {
        const v = t.validacion || {};
        const cls = v.coincide_bd ? 'txt-ok' : 'txt-err';
        const obs = (v.observaciones || []).map(o => `<li>${o}</li>`).join('');
        return `<div class="ticket-item">
          <div><b>${t.ticket_id}</b> · ${t.po_id} · <code>${t.sku}</code> (${t.ordered_qty} ${t.unit})</div>
          <div class="${cls}">${v.validacion_bd || ''} ${v.ot_generada_id ? '· OT #' + v.ot_generada_id : ''}</div>
          <ul style="margin:4px 0 0 18px;">${obs}</ul>
          ${t.jpg_url ? `<a href="${t.jpg_url}" target="_blank">Ver JPG</a>` : ''}
        </div>`;
      }).join('');
      refreshDashboard();
    }

    async function simularPaso(color, qr = '') {
      await fetch(`/api/simular_paso_banda?color=${encodeURIComponent(color)}&qr=${encodeURIComponent(qr)}`, { method: 'POST' });
      refreshDashboard();
    }

    async function resetDemo() {
      await fetch('/api/reset_demo', { method: 'POST' });
      refreshDashboard();
    }

    setInterval(refreshDashboard, 1500);
    refreshDashboard();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_UI
