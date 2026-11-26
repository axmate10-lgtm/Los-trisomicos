import os
import subprocess
import sys

PROJECT_DIR = "cedis_iot_demo"

FILES = {
    "database.py": '''import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "trisomicos_bd.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS estado_oc (
            ID_ESTADO_OC INTEGER PRIMARY KEY,
            NOMBRE_ESTADO_OC TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS frecuencia_entrega (
            ID_FRECUENCIA INTEGER PRIMARY KEY,
            NOMBRE_FRECUENCIA TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS estado_lote (
            ID_ESTADO_LOTE INTEGER PRIMARY KEY,
            NOMBRE_ESTADO_LOTE TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS tipo_incidencia (
            ID_TIPO_INCIDENCIA INTEGER PRIMARY KEY,
            NOMBRE_TIPO_INCIDENCIA TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS estado_orden_trabajo (
            ID_ESTADO_ORDEN_TRABAJO INTEGER PRIMARY KEY,
            NOMBRE_ESTADO_ORDEN_TRABAJO TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS proveedor (
            ID_PROVEEDOR INTEGER PRIMARY KEY AUTOINCREMENT,
            NOMBRE_PROVEEDOR TEXT NOT NULL,
            RFC TEXT,
            CONTACTO TEXT,
            TELEFONO TEXT
        );

        CREATE TABLE IF NOT EXISTS producto (
            ID_PRODUCTO INTEGER PRIMARY KEY AUTOINCREMENT,
            CODIGO_SKU TEXT NOT NULL UNIQUE,
            NOMBRE_PRODUCTO TEXT NOT NULL,
            UNIDAD_MEDIDA TEXT NOT NULL,
            COSTO_UNITARIO REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS color_producto (
            ID_COLOR_PRODUCTO INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_PRODUCTO INTEGER NOT NULL,
            ID_PROVEEDOR INTEGER NOT NULL,
            NOMBRE_COLOR TEXT NOT NULL,
            CODIGO_HEX TEXT NOT NULL,
            FOREIGN KEY (ID_PRODUCTO) REFERENCES producto(ID_PRODUCTO),
            FOREIGN KEY (ID_PROVEEDOR) REFERENCES proveedor(ID_PROVEEDOR)
        );

        CREATE TABLE IF NOT EXISTS orden_compra (
            ID_OC INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_PROVEEDOR INTEGER NOT NULL,
            ID_ESTADO_OC INTEGER NOT NULL,
            ID_FRECUENCIA INTEGER NOT NULL,
            FECHA_EMISION TEXT NOT NULL,
            FOREIGN KEY (ID_PROVEEDOR) REFERENCES proveedor(ID_PROVEEDOR),
            FOREIGN KEY (ID_ESTADO_OC) REFERENCES estado_oc(ID_ESTADO_OC),
            FOREIGN KEY (ID_FRECUENCIA) REFERENCES frecuencia_entrega(ID_FRECUENCIA)
        );

        CREATE TABLE IF NOT EXISTS orden_compra_detalle (
            ID_DETALLE INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_OC INTEGER NOT NULL,
            ID_PRODUCTO INTEGER NOT NULL,
            CANTIDAD_SOLICITADA INTEGER NOT NULL,
            FOREIGN KEY (ID_OC) REFERENCES orden_compra(ID_OC),
            FOREIGN KEY (ID_PRODUCTO) REFERENCES producto(ID_PRODUCTO)
        );

        CREATE TABLE IF NOT EXISTS lote_recepcion (
            ID_LOTE INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_OC INTEGER NOT NULL,
            ID_ESTADO_LOTE INTEGER NOT NULL,
            CANTIDAD_CAJAS_ESPERADA INTEGER NOT NULL,
            CANTIDAD_CAJAS_CONTADA INTEGER NOT NULL DEFAULT 0,
            FECHA_RECEPCION TEXT NOT NULL,
            FOREIGN KEY (ID_OC) REFERENCES orden_compra(ID_OC),
            FOREIGN KEY (ID_ESTADO_LOTE) REFERENCES estado_lote(ID_ESTADO_LOTE)
        );

        CREATE TABLE IF NOT EXISTS caja (
            ID_CAJA INTEGER PRIMARY KEY AUTOINCREMENT,
            CODIGO_CAJA TEXT NOT NULL UNIQUE,
            ID_LOTE INTEGER NOT NULL,
            ID_COLOR_PRODUCTO INTEGER NOT NULL,
            ESTADO_INSPECCION TEXT NOT NULL,
            CANTIDAD_REAL INTEGER NOT NULL,
            RUTA_ASIGNADA TEXT NOT NULL,
            LEIDA INTEGER NOT NULL DEFAULT 0,
            FECHA_LECTURA_BANDA TEXT,
            FOREIGN KEY (ID_LOTE) REFERENCES lote_recepcion(ID_LOTE),
            FOREIGN KEY (ID_COLOR_PRODUCTO) REFERENCES color_producto(ID_COLOR_PRODUCTO)
        );

        CREATE TABLE IF NOT EXISTS lectura_banda (
            ID_LECTURA INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_CAJA INTEGER NOT NULL,
            COLOR_DETECTADO TEXT NOT NULL,
            QR_DETECTADO TEXT,
            RUTA_ACCIONADA TEXT NOT NULL,
            TIMESTAMP_LECTURA TEXT NOT NULL,
            RESULTADO TEXT NOT NULL,
            FOREIGN KEY (ID_CAJA) REFERENCES caja(ID_CAJA)
        );

        CREATE TABLE IF NOT EXISTS orden_trabajo (
            ID_OT INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_LOTE INTEGER NOT NULL,
            ID_TIPO_INCIDENCIA INTEGER NOT NULL,
            ID_ESTADO_ORDEN_TRABAJO INTEGER NOT NULL,
            DESCRIPCION TEXT NOT NULL,
            FECHA_CREACION TEXT NOT NULL,
            FOREIGN KEY (ID_LOTE) REFERENCES lote_recepcion(ID_LOTE),
            FOREIGN KEY (ID_TIPO_INCIDENCIA) REFERENCES tipo_incidencia(ID_TIPO_INCIDENCIA),
            FOREIGN KEY (ID_ESTADO_ORDEN_TRABAJO) REFERENCES estado_orden_trabajo(ID_ESTADO_ORDEN_TRABAJO)
        );

        CREATE TABLE IF NOT EXISTS tickets_simulados (
            ID_TICKET INTEGER PRIMARY KEY AUTOINCREMENT,
            TICKET_ID TEXT NOT NULL UNIQUE,
            PO_ID TEXT NOT NULL,
            SUPPLIER TEXT NOT NULL,
            SKU TEXT NOT NULL,
            UNIT TEXT NOT NULL,
            ORDERED_QTY INTEGER NOT NULL,
            RECEIVED_QTY INTEGER NOT NULL,
            MEASURED_QTY INTEGER NOT NULL,
            DELTA_VS_ORDER INTEGER NOT NULL,
            UNIT_COST_MXN REAL NOT NULL,
            LOT TEXT NOT NULL,
            SCENARIO TEXT NOT NULL,
            STATUS TEXT NOT NULL,
            RECOMMENDED_ACTION TEXT NOT NULL,
            LINKED_WO TEXT,
            CREATED_AT TEXT NOT NULL
        );
        """
    )

    cur.executemany(
        "INSERT OR IGNORE INTO estado_oc VALUES (?, ?)",
        [(1, "EMITIDA"), (2, "EN_RECEPCION"), (3, "CERRADA")],
    )
    cur.executemany(
        "INSERT OR IGNORE INTO frecuencia_entrega VALUES (?, ?)",
        [(1, "UNICA"), (2, "SEMANAL"), (3, "QUINCENAL")],
    )
    cur.executemany(
        "INSERT OR IGNORE INTO estado_lote VALUES (?, ?)",
        [(1, "EN_RECEPCION"), (2, "COMPLETO"), (3, "INCOMPLETO"), (4, "EXCEDENTE")],
    )
    cur.executemany(
        "INSERT OR IGNORE INTO tipo_incidencia VALUES (?, ?)",
        [(1, "CAJA_DANADA_O_INCORRECTA"), (2, "FALTANTE"), (3, "NO_COINCIDE_OC"), (4, "EXCEDENTE")],
    )
    cur.executemany(
        "INSERT OR IGNORE INTO estado_orden_trabajo VALUES (?, ?)",
        [(1, "ABIERTA"), (2, "EN_REVISION"), (3, "RESUELTA")],
    )

    if cur.execute("SELECT COUNT(*) FROM proveedor").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO proveedor (ID_PROVEEDOR, NOMBRE_PROVEEDOR, RFC, CONTACTO, TELEFONO) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Aceros del Norte SA", "ANO920312H11", "Carlos Mendez", "229-110-2030"),
                (2, "Plasticos Industriales MX", "PIM880514K90", "Laura Gomez", "229-440-8899"),
                (3, "ElectroComponentes Veracruz", "ECV010922M45", "Luis Ortega", "229-778-1122"),
            ],
        )

    if cur.execute("SELECT COUNT(*) FROM producto").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO producto (ID_PRODUCTO, CODIGO_SKU, NOMBRE_PRODUCTO, UNIDAD_MEDIDA, COSTO_UNITARIO) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "TORN_M6X20", "Tornillo Hexagonal M6x20", "CAJA", 450.0),
                (2, "VALV_PVC_2", "Valvula PVC 2 Pulgadas", "CAJA", 780.0),
                (3, "CABLE_THW_12", "Rollo Cable THW Cal 12", "ROLLO", 1120.0),
                (4, "SENSOR_IND_12V", "Sensor Inductivo 12V NPN", "CAJA", 1650.0),
                (5, "CONECTOR_RJ45", "Caja Conectores RJ45 Cat6", "CAJA", 320.0),
            ],
        )

    if cur.execute("SELECT COUNT(*) FROM color_producto").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO color_producto (ID_COLOR_PRODUCTO, ID_PRODUCTO, ID_PROVEEDOR, NOMBRE_COLOR, CODIGO_HEX) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 1, "AZUL", "#2563EB"),
                (2, 2, 2, "NARANJA", "#F97316"),
                (3, 3, 3, "VERDE", "#16A34A"),
                (4, 4, 3, "AMARILLO", "#EAB308"),
                (5, 5, 1, "MORADO", "#9333EA"),
            ],
        )

    if cur.execute("SELECT COUNT(*) FROM orden_compra").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO orden_compra (ID_OC, ID_PROVEEDOR, ID_ESTADO_OC, ID_FRECUENCIA, FECHA_EMISION) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 2, 2, "2026-11-25"),
                (2, 2, 2, 1, "2026-11-25"),
                (3, 3, 2, 2, "2026-11-25"),
            ],
        )
        cur.executemany(
            "INSERT INTO orden_compra_detalle (ID_OC, ID_PRODUCTO, CANTIDAD_SOLICITADA) VALUES (?, ?, ?)",
            [
                (1, 1, 5),
                (2, 2, 4),
                (3, 3, 6),
            ],
        )
        cur.executemany(
            "INSERT INTO lote_recepcion (ID_LOTE, ID_OC, ID_ESTADO_LOTE, CANTIDAD_CAJAS_ESPERADA, CANTIDAD_CAJAS_CONTADA, FECHA_RECEPCION) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, 1, 1, 5, 0, "2026-11-25"),
                (2, 2, 1, 4, 0, "2026-11-25"),
                (3, 3, 1, 6, 0, "2026-11-25"),
            ],
        )

    conn.commit()
    conn.close()
''',

    "ticket_generator.py": '''import random
from datetime import datetime

CATALOGO_SIM = [
    {"po_id": "OC-101", "supplier": "Aceros del Norte SA", "sku": "TORN_M6X20", "unit": "CAJA", "cost": 450.0, "lot": "LOTE-01"},
    {"po_id": "OC-102", "supplier": "Plasticos Industriales MX", "sku": "VALV_PVC_2", "unit": "CAJA", "cost": 780.0, "lot": "LOTE-02"},
    {"po_id": "OC-103", "supplier": "ElectroComponentes Veracruz", "sku": "CABLE_THW_12", "unit": "ROLLO", "cost": 1120.0, "lot": "LOTE-03"},
]

ESCENARIOS = [
    ("CORRECTO", "APROBADO", "Ingresar a ubicacion A-01"),
    ("INCORRECTO", "RETENIDO_SERVO_2", "Desviar con Servo 2 y abrir incidencia"),
    ("DANADO", "RETENIDO_SERVO_1", "Desviar con Servo 1 a cuarentena"),
    ("DIFIERE_PARCIAL", "INCIDENCIA_FALTANTE", "Notificar faltante a Compras"),
    ("DIFIERE_EXCEDENTE", "INCIDENCIA_EXCEDENTE", "Retener excedente en muelle"),
]


def generar_lote_tickets(cantidad=5):
    resultados = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _ in range(cantidad):
        item = random.choice(CATALOGO_SIM)
        scenario, status, action = random.choice(ESCENARIOS)
        ordered = random.randint(4, 10)
        if scenario == "CORRECTO":
            received = ordered
            measured = ordered
        elif scenario == "DIFIERE_PARCIAL":
            received = max(1, ordered - random.randint(1, 3))
            measured = received
        elif scenario == "DIFIERE_EXCEDENTE":
            received = ordered + random.randint(1, 3)
            measured = received
        else:
            received = ordered
            measured = ordered

        delta = measured - ordered
        tid = f"TCK-{datetime.now().strftime('%H%M%S')}-{random.randint(100, 999)}"
        wo = None if scenario == "CORRECTO" else f"OT-{random.randint(1000, 9999)}"

        resultados.append(
            {
                "ticket_id": tid,
                "po_id": item["po_id"],
                "supplier": item["supplier"],
                "sku": item["sku"],
                "unit": item["unit"],
                "ordered_qty": ordered,
                "received_qty": received,
                "measured_qty": measured,
                "delta_vs_order": delta,
                "unit_cost_mxn": item["cost"],
                "lot": item["lot"],
                "scenario": scenario,
                "status": status,
                "recommended_action": action,
                "linked_wo": wo,
                "timestamp": now,
            }
        )
    return resultados
''',

    "vision_engine.py": '''import threading
import time
import cv2
import numpy as np

COLOR_RANGES_HSV = {
    "AZUL":     {"lower": np.array([92, 65, 65]),   "upper": np.array([122, 255, 255]), "bgr": (255, 120, 0)},
    "MORADO":   {"lower": np.array([123, 55, 50]),  "upper": np.array([158, 255, 255]), "bgr": (180, 50, 140)},
    "VERDE":    {"lower": np.array([42, 55, 60]),   "upper": np.array([88, 255, 255]),  "bgr": (60, 180, 40)},
    "AMARILLO": {"lower": np.array([22, 70, 80]),   "upper": np.array([38, 255, 255]),  "bgr": (0, 220, 255)},
    "NARANJA":  {"lower": np.array([6, 75, 85]),    "upper": np.array([21, 255, 255]),  "bgr": (0, 130, 255)},
}


class VisionSystem:
    def __init__(self, on_detection_callback=None):
        self.cap = None
        self.running = False
        self.lock = threading.Lock()
        self.raw_jpeg = None
        self.filtered_jpeg = None
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

    def start(self, camera_index=0):
        if self.running:
            return
        self.cap = (
            cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if hasattr(cv2, "CAP_DSHOW")
            else cv2.VideoCapture(camera_index)
        )
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def _make_placeholder(self, text):
        img = np.zeros((360, 480, 3), dtype=np.uint8)
        cv2.putText(img, text, (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
        _, buf = cv2.imencode(".jpg", img)
        return buf.tobytes()

    def _draw_red_grids(self, img, now):
        h, w = img.shape[:2]

        # 1. Cuadricula Roja Central: ZONA DE DISPARO / PASO DE CAJA
        x1, y1 = int(w * 0.30), int(h * 0.28)
        x2, y2 = int(w * 0.70), int(h * 0.78)

        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        cv2.line(img, (mid_x, y1), (mid_x, y2), (0, 0, 180), 1)
        cv2.line(img, (x1, mid_y), (x2, mid_y), (0, 0, 180), 1)
        cv2.putText(img, "ZONA DISPARO BANDA", (x1 + 8, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 255), 2)

        # 2. Cuadricula Roja Izquierda: SERVO 1 (CAJA DANADA)
        s1_x1, s1_y1, s1_x2, s1_y2 = 12, int(h * 0.32), int(w * 0.26), int(h * 0.74)
        s1_active = (self.servo_state == "SERVO_1") and (now < self.flash_until)
        if s1_active:
            overlay = img.copy()
            cv2.rectangle(overlay, (s1_x1, s1_y1), (s1_x2, s1_y2), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)
        cv2.rectangle(img, (s1_x1, s1_y1), (s1_x2, s1_y2), (0, 0, 255), 2)
        cv2.putText(img, "SERVO 1", (s1_x1 + 12, s1_y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255) if s1_active else (0, 0, 255), 2)
        cv2.putText(img, "DANADA", (s1_x1 + 12, s1_y1 + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 255), 1)
        cv2.putText(img, "ACTIVO!" if s1_active else "OFF", (s1_x1 + 12, s1_y2 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255) if s1_active else (120, 120, 120), 2)

        # 3. Cuadricula Roja Derecha: SERVO 2 (PRODUCTO NO ESPERADO / INCORRECTO)
        s2_x1, s2_y1, s2_x2, s2_y2 = int(w * 0.74), int(h * 0.32), w - 12, int(h * 0.74)
        s2_active = (self.servo_state == "SERVO_2") and (now < self.flash_until)
        if s2_active:
            overlay = img.copy()
            cv2.rectangle(overlay, (s2_x1, s2_y1), (s2_x2, s2_y2), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.45, img, 0.55, 0, img)
        cv2.rectangle(img, (s2_x1, s2_y1), (s2_x2, s2_y2), (0, 0, 255), 2)
        cv2.putText(img, "SERVO 2", (s2_x1 + 12, s2_y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255) if s2_active else (0, 0, 255), 2)
        cv2.putText(img, "NO ESPERADO", (s2_x1 + 8, s2_y1 + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (200, 200, 255), 1)
        cv2.putText(img, "ACTIVO!" if s2_active else "OFF", (s2_x1 + 12, s2_y2 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255) if s2_active else (120, 120, 120), 2)

        # 4. Barra inferior de estado de paso, servo y conteo
        cv2.rectangle(img, (0, h - 42), (w, h), (15, 23, 42), -1)
        paso_color = (0, 255, 0) if now < self.flash_until else (0, 220, 255)
        texto_paso = ">>> CAJA REGISTRADA - PUEDE PASAR <<<" if now < self.flash_until else "COLOCA ETIQUETA EN CUADRICULA CENTRAL"
        cv2.putText(img, texto_paso, (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.50, paso_color, 2)
        cv2.putText(img, f"CONTEO: {self.lote_conteo_texto}", (w - 175, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2)

    def _loop(self):
        kernel = np.ones((5, 5), np.uint8)
        while self.running:
            if not self.cap or not self.cap.isOpened():
                placeholder = self._make_placeholder("Camara no disponible")
                with self.lock:
                    self.raw_jpeg = placeholder
                    self.filtered_jpeg = placeholder
                time.sleep(0.5)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
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
                            0.55,
                            cfg["bgr"],
                            2,
                        )

            filtered_display = cv2.bitwise_and(frame, frame, mask=combined_mask)
            now = time.time()
            self._draw_red_grids(filtered_display, now)
            cv2.rectangle(raw_display, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 0, 255), 2)

            cv2.putText(
                filtered_display,
                f"FILTRO [{self.active_color_filter}] | COLOR: {detected_color} | {self.servo_label}",
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
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

            _, buf_raw = cv2.imencode(".jpg", raw_display, [cv2.IMWRITE_JPEG_QUALITY, 80])
            _, buf_flt = cv2.imencode(".jpg", filtered_display, [cv2.IMWRITE_JPEG_QUALITY, 80])

            with self.lock:
                self.raw_jpeg = buf_raw.tobytes()
                self.filtered_jpeg = buf_flt.tobytes()

            time.sleep(0.03)
''',

    "app.py": '''import base64
import io
import time
from datetime import datetime
from typing import Optional

import qrcode
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import get_connection, init_db
from ticket_generator import generar_lote_tickets
from vision_engine import VisionSystem

app = FastAPI(title="CEDIS IoT - Control de Almacen y Vision Artificial")
init_db()

ACTIVE_SESSION = {
    "id_lote": 1,
    "auto_scan_enabled": True,
    "last_event": "Sistema listo. Coloca una etiqueta dentro de la cuadricula roja central.",
    "last_route": "STANDBY",
    "servo_activado": "NINGUNO (NORMAL)",
    "conteo_actual": "0 / 5",
}


def sincronizar_conteo_lote(id_lote: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT CANTIDAD_CAJAS_CONTADA, CANTIDAD_CAJAS_ESPERADA FROM lote_recepcion WHERE ID_LOTE = ?",
        (id_lote,),
    ).fetchone()
    conn.close()
    if row:
        txt = f"{row['CANTIDAD_CAJAS_CONTADA']} / {row['CANTIDAD_CAJAS_ESPERADA']}"
        ACTIVE_SESSION["conteo_actual"] = txt
        vision.lote_conteo_texto = txt


def registrar_lectura_banda(color_detectado: str, qr_detectado: str = ""):
    if not ACTIVE_SESSION["auto_scan_enabled"]:
        return

    conn = get_connection()
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    id_lote = ACTIVE_SESSION["id_lote"]

    try:
        qr_codigo = None
        qr_estado = "CORRECTO"
        if qr_detectado and "|" in qr_detectado:
            parts = qr_detectado.split("|")
            qr_codigo = parts[0]
            if len(parts) > 1 and parts[1]:
                color_detectado = parts[1]
            if len(parts) > 2 and parts[2]:
                qr_estado = parts[2]

        cp = cur.execute(
            """
            SELECT cp.ID_COLOR_PRODUCTO, cp.ID_PRODUCTO, cp.ID_PROVEEDOR, cp.NOMBRE_COLOR,
                   p.NOMBRE_PRODUCTO, pr.NOMBRE_PROVEEDOR
            FROM color_producto cp
            JOIN producto p ON p.ID_PRODUCTO = cp.ID_PRODUCTO
            JOIN proveedor pr ON pr.ID_PROVEEDOR = cp.ID_PROVEEDOR
            WHERE cp.NOMBRE_COLOR = ?
            """,
            (color_detectado,),
        ).fetchone()

        if not cp:
            ACTIVE_SESSION["last_event"] = f"[{now_str}] Lectura ignorada: color '{color_detectado}' no catalogado."
            return

        lote_info = cur.execute(
            """
            SELECT lr.ID_LOTE, lr.CANTIDAD_CAJAS_ESPERADA, lr.CANTIDAD_CAJAS_CONTADA,
                   oc.ID_PROVEEDOR AS OC_PROV, ocd.ID_PRODUCTO AS OC_PROD
            FROM lote_recepcion lr
            JOIN orden_compra oc ON oc.ID_OC = lr.ID_OC
            JOIN orden_compra_detalle ocd ON ocd.ID_OC = oc.ID_OC
            WHERE lr.ID_LOTE = ?
            """,
            (id_lote,),
        ).fetchone()

        coincide_oc = (
            lote_info
            and cp["ID_PRODUCTO"] == lote_info["OC_PROD"]
            and cp["ID_PROVEEDOR"] == lote_info["OC_PROV"]
        )

        if qr_estado == "DANADO":
            servo = "SERVO_1"
            servo_desc = "SERVO 1 (CAJA DANADA)"
            ruta = "SERVO_1_DANADA"
            resultado = "RETENIDA_DANADA"
            estado_caja = "DANADO"
        elif qr_estado == "INCORRECTO" or not coincide_oc:
            servo = "SERVO_2"
            servo_desc = "SERVO 2 (NO ESPERADO)"
            ruta = "SERVO_2_NO_ESPERADO"
            resultado = "RETENIDA_NO_ESPERADO"
            estado_caja = "INCORRECTO"
        else:
            servo = "NINGUNO"
            servo_desc = "NINGUNO (NORMAL - PASA)"
            ruta = "NORMAL_ALMACEN_OK"
            resultado = "EXITOSA"
            estado_caja = "CORRECTO"

        codigo_final = qr_codigo or f"CJ-{datetime.now().strftime('%H%M%S')}-{int(time.time()*10)%100}"

        existe = cur.execute("SELECT ID_CAJA FROM caja WHERE CODIGO_CAJA = ?", (codigo_final,)).fetchone()
        if existe:
            vision.servo_state = "SERVO_2"
            vision.servo_label = "SERVO 2 (DUPLICADO)"
            ACTIVE_SESSION["servo_activado"] = "SERVO 2 (DUPLICADO)"
            ACTIVE_SESSION["last_event"] = f"[{now_str}] ALERTA DUPLICADO: {codigo_final} -> SERVO 2."
            return

        cur.execute(
            """
            INSERT INTO caja (CODIGO_CAJA, ID_LOTE, ID_COLOR_PRODUCTO, ESTADO_INSPECCION, CANTIDAD_REAL, RUTA_ASIGNADA, LEIDA, FECHA_LECTURA_BANDA)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (codigo_final, id_lote, cp["ID_COLOR_PRODUCTO"], estado_caja, 1, ruta, now_str),
        )
        id_caja = cur.lastrowid

        cur.execute(
            """
            INSERT INTO lectura_banda (ID_CAJA, COLOR_DETECTADO, QR_DETECTADO, RUTA_ACCIONADA, TIMESTAMP_LECTURA, RESULTADO)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id_caja, color_detectado, qr_detectado or codigo_final, ruta, now_str, resultado),
        )

        nuevo_conteo = (lote_info["CANTIDAD_CAJAS_CONTADA"] or 0) + 1
        esperadas = lote_info["CANTIDAD_CAJAS_ESPERADA"]
        nuevo_estado_lote = 1
        if nuevo_conteo == esperadas:
            nuevo_estado_lote = 2
        elif nuevo_conteo > esperadas:
            nuevo_estado_lote = 4

        cur.execute(
            "UPDATE lote_recepcion SET CANTIDAD_CAJAS_CONTADA = ?, ID_ESTADO_LOTE = ? WHERE ID_LOTE = ?",
            (nuevo_conteo, nuevo_estado_lote, id_lote),
        )

        if servo != "NINGUNO":
            cur.execute(
                """
                INSERT INTO orden_trabajo (ID_LOTE, ID_TIPO_INCIDENCIA, ID_ESTADO_ORDEN_TRABAJO, DESCRIPCION, FECHA_CREACION)
                VALUES (?, 1, 1, ?, ?)
                """,
                (id_lote, f"{servo_desc}: Caja {codigo_final} ({cp['NOMBRE_COLOR']} - {cp['NOMBRE_PRODUCTO']})", now_str),
            )
        elif nuevo_conteo > esperadas:
            cur.execute(
                """
                INSERT INTO orden_trabajo (ID_LOTE, ID_TIPO_INCIDENCIA, ID_ESTADO_ORDEN_TRABAJO, DESCRIPCION, FECHA_CREACION)
                VALUES (?, 4, 1, ?, ?)
                """,
                (id_lote, f"Lote {id_lote} excedido ({nuevo_conteo}/{esperadas} cajas)", now_str),
            )

        conn.commit()

        conteo_txt = f"{nuevo_conteo} / {esperadas}"
        vision.servo_state = servo
        vision.servo_label = servo_desc
        vision.lote_conteo_texto = conteo_txt

        ACTIVE_SESSION["servo_activado"] = servo_desc
        ACTIVE_SESSION["conteo_actual"] = conteo_txt
        ACTIVE_SESSION["last_route"] = ruta
        ACTIVE_SESSION["last_event"] = (
            f"[{now_str}] PASA CAJA #{nuevo_conteo}/{esperadas} | {cp['NOMBRE_COLOR']} ({cp['NOMBRE_PRODUCTO']}) -> {servo_desc}"
        )
    finally:
        conn.close()


vision = VisionSystem(on_detection_callback=registrar_lectura_banda)


@app.on_event("startup")
def startup_event():
    sincronizar_conteo_lote(ACTIVE_SESSION["id_lote"])
    vision.start(1)


@app.on_event("shutdown")
def shutdown_event():
    vision.stop()


class InspeccionCajaIn(BaseModel):
    id_lote: int
    id_color_producto: int
    estado_inspeccion: str
    cantidad_real: int


class ConfigVisionIn(BaseModel):
    id_lote: Optional[int] = None
    color_filter: Optional[str] = None
    auto_scan: Optional[bool] = None


def gen_mjpeg(stream_type: str):
    while True:
        with vision.lock:
            frame = vision.raw_jpeg if stream_type == "raw" else vision.filtered_jpeg
        if frame:
            yield (b"--frame\\r\\nContent-Type: image/jpeg\\r\\n\\r\\n" + frame + b"\\r\\n")
        time.sleep(0.04)


@app.get("/video/raw")
def video_raw():
    return StreamingResponse(gen_mjpeg("raw"), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/video/filtered")
def video_filtered():
    return StreamingResponse(gen_mjpeg("filtered"), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/dashboard")
def get_dashboard():
    conn = get_connection()
    cur = conn.cursor()

    lotes = [
        dict(r)
        for r in cur.execute(
            """
            SELECT lr.ID_LOTE, lr.ID_OC, pr.NOMBRE_PROVEEDOR, p.NOMBRE_PRODUCTO,
                   cp.NOMBRE_COLOR, cp.CODIGO_HEX, cp.ID_COLOR_PRODUCTO,
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
        ).fetchall()
    ]

    colores = [
        dict(r)
        for r in cur.execute(
            """
            SELECT cp.*, p.NOMBRE_PRODUCTO, pr.NOMBRE_PROVEEDOR
            FROM color_producto cp
            JOIN producto p ON p.ID_PRODUCTO = cp.ID_PRODUCTO
            JOIN proveedor pr ON pr.ID_PROVEEDOR = cp.ID_PROVEEDOR
            """
        ).fetchall()
    ]

    lecturas = [
        dict(r)
        for r in cur.execute(
            """
            SELECT lb.ID_LECTURA, c.CODIGO_CAJA, c.ID_LOTE, lb.COLOR_DETECTADO,
                   c.ESTADO_INSPECCION, lb.RUTA_ACCIONADA, lb.RESULTADO, lb.TIMESTAMP_LECTURA
            FROM lectura_banda lb
            JOIN caja c ON c.ID_CAJA = lb.ID_CAJA
            ORDER BY lb.ID_LECTURA DESC LIMIT 15
            """
        ).fetchall()
    ]

    ordenes_trabajo = [
        dict(r)
        for r in cur.execute(
            """
            SELECT ot.ID_OT, ot.ID_LOTE, ti.NOMBRE_TIPO_INCIDENCIA, eot.NOMBRE_ESTADO_ORDEN_TRABAJO,
                   ot.DESCRIPCION, ot.FECHA_CREACION
            FROM orden_trabajo ot
            JOIN tipo_incidencia ti ON ti.ID_TIPO_INCIDENCIA = ot.ID_TIPO_INCIDENCIA
            JOIN estado_orden_trabajo eot ON eot.ID_ESTADO_ORDEN_TRABAJO = ot.ID_ESTADO_ORDEN_TRABAJO
            ORDER BY ot.ID_OT DESC LIMIT 10
            """
        ).fetchall()
    ]

    tickets = [
        dict(r)
        for r in cur.execute(
            "SELECT * FROM tickets_simulados ORDER BY ID_TICKET DESC LIMIT 15"
        ).fetchall()
    ]

    conn.close()
    return {
        "session": ACTIVE_SESSION,
        "vision_live": {
            "detected_color": vision.current_color,
            "detected_qr": vision.current_qr,
            "filter": vision.active_color_filter,
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
    conn = get_connection()
    cur = conn.cursor()
    cp = cur.execute(
        """
        SELECT cp.*, p.NOMBRE_PRODUCTO, pr.NOMBRE_PROVEEDOR
        FROM color_producto cp
        JOIN producto p ON p.ID_PRODUCTO = cp.ID_PRODUCTO
        JOIN proveedor pr ON pr.ID_PROVEEDOR = cp.ID_PROVEEDOR
        WHERE cp.ID_COLOR_PRODUCTO = ?
        """,
        (data.id_color_producto,),
    ).fetchone()
    conn.close()

    if not cp:
        raise HTTPException(status_code=404, detail="Color/Producto no encontrado")

    codigo_caja = f"CJ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if data.estado_inspeccion == "DANADO":
        ruta = "SERVO_1_DANADA"
    elif data.estado_inspeccion == "INCORRECTO":
        ruta = "SERVO_2_NO_ESPERADO"
    else:
        ruta = "NINGUNO (NORMAL)"

    qr_payload = f"{codigo_caja}|{cp['NOMBRE_COLOR']}|{data.estado_inspeccion}"

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "codigo_caja": codigo_caja,
        "qr_payload": qr_payload,
        "qr_base64": qr_b64,
        "color": cp["NOMBRE_COLOR"],
        "hex": cp["CODIGO_HEX"],
        "producto": cp["NOMBRE_PRODUCTO"],
        "proveedor": cp["NOMBRE_PROVEEDOR"],
        "estado": data.estado_inspeccion,
        "cantidad_real": data.cantidad_real,
        "ruta": ruta,
    }


@app.post("/api/tickets/random")
def crear_tickets_random(cantidad: int = 5):
    tickets = generar_lote_tickets(cantidad=cantidad)
    conn = get_connection()
    cur = conn.cursor()
    for t in tickets:
        cur.execute(
            """
            INSERT OR IGNORE INTO tickets_simulados
            (TICKET_ID, PO_ID, SUPPLIER, SKU, UNIT, ORDERED_QTY, RECEIVED_QTY, MEASURED_QTY,
             DELTA_VS_ORDER, UNIT_COST_MXN, LOT, SCENARIO, STATUS, RECOMMENDED_ACTION, LINKED_WO, CREATED_AT)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t["ticket_id"], t["po_id"], t["supplier"], t["sku"], t["unit"],
                t["ordered_qty"], t["received_qty"], t["measured_qty"], t["delta_vs_order"],
                t["unit_cost_mxn"], t["lot"], t["scenario"], t["status"],
                t["recommended_action"], t["linked_wo"], t["timestamp"],
            ),
        )
    conn.commit()
    conn.close()
    return {"generados": len(tickets), "tickets": tickets}


@app.post("/api/simular_paso_banda")
def simular_paso_banda(color: str, qr: str = ""):
    vision.last_trigger_time = 0
    vision.flash_until = time.time() + 1.8
    registrar_lectura_banda(color, qr)
    return {"ok": True, "session": ACTIVE_SESSION}


@app.post("/api/reset_demo")
def reset_demo():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM lectura_banda")
    cur.execute("DELETE FROM caja")
    cur.execute("DELETE FROM orden_trabajo")
    cur.execute("DELETE FROM tickets_simulados")
    cur.execute("UPDATE lote_recepcion SET CANTIDAD_CAJAS_CONTADA = 0, ID_ESTADO_LOTE = 1")
    conn.commit()
    conn.close()
    vision.servo_state = "NINGUNO"
    vision.servo_label = "REPOSO (PASA NORMAL)"
    sincronizar_conteo_lote(ACTIVE_SESSION["id_lote"])
    ACTIVE_SESSION["last_event"] = "Base operativa reiniciada."
    ACTIVE_SESSION["last_route"] = "STANDBY"
    ACTIVE_SESSION["servo_activado"] = "NINGUNO (NORMAL)"
    return {"ok": True}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()
''',

    "static/index.html": '''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>CEDIS IoT — Centro de Control, Visión Artificial y Servos</title>
  <style>
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0b1120; color: #e2e8f0; margin: 0; padding: 16px; }
    h1, h2, h3 { margin: 0 0 10px 0; color: #38bdf8; }
    .topbar { display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 12px 18px; border-radius: 10px; margin-bottom: 14px; border: 1px solid #334155; }
    .badge { padding: 4px 10px; border-radius: 999px; font-weight: bold; font-size: 12px; background: #0284c7; color: #fff; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 14px; }
    .video-box { width: 100%; border-radius: 8px; border: 2px solid #334155; background: #000; display: block; }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
    select, input, button { background: #0f172a; color: #f8fafc; border: 1px solid #475569; padding: 7px 11px; border-radius: 6px; font-size: 13px; }
    button { background: #2563eb; border: none; font-weight: 600; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    button.warn { background: #dc2626; }
    button.ok { background: #16a34a; }
    table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }
    th, td { border-bottom: 1px solid #334155; padding: 7px 8px; text-align: left; }
    th { color: #94a3b8; background: #0f172a; }
    .status-bar { background: #0f172a; border-left: 4px solid #22c55e; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; font-size: 13.5px; }
    .qr-preview { display: flex; gap: 14px; align-items: center; margin-top: 10px; background: #0f172a; padding: 10px; border-radius: 8px; }
  </style>
</head>
<body>
  <div class="topbar">
    <div>
      <h1>CEDIS IoT — Recepción, Visión HSV y Control de Servos</h1>
      <small style="color:#94a3b8;">Servo 1: Dañada | Servo 2: Producto No Esperado | Normal: Reposo</small>
    </div>
    <div>
      <span class="badge" id="badge-conteo">CONTEO: 0 / 5</span>
      <span class="badge" style="background:#7c3aed;" id="badge-servo">SERVO: NINGUNO</span>
    </div>
  </div>

  <div class="status-bar">
    <div id="last-event">Cargando estado del sistema...</div>
    <div>
      <button class="warn" onclick="resetDemo()">Reiniciar Demo</button>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>Streaming Cámara Real (Detección de Cajas, Color y QR)</h3>
      <img class="video-box" src="/video/raw" />
      <div class="controls">
        <label>Lote activo en banda:</label>
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
      <h3>Muelle de Descarga — Inspección y Etiqueta QR</h3>
      <div class="controls">
        <select id="ins-color"></select>
        <select id="ins-estado">
          <option value="CORRECTO">CORRECTO (Normal)</option>
          <option value="DANADO">DAÑADO (Activa Servo 1)</option>
          <option value="INCORRECTO">INCORRECTO (Activa Servo 2)</option>
        </select>
        <input type="number" id="ins-cant" value="1" min="1" style="width:65px;" />
        <button onclick="generarEtiqueta()">Generar Etiqueta QR</button>
      </div>
      <div class="qr-preview" id="qr-box" style="display:none;">
        <img id="qr-img" width="110" height="110" style="background:#fff; padding:4px; border-radius:6px;" />
        <div id="qr-info" style="font-size:13px; line-height:1.5;"></div>
      </div>
    </div>

    <div class="card">
      <h3>Simulador de Tickets de Recepción (trisomicos_bd)</h3>
      <div class="controls">
        <button onclick="generarTickets(5)">Generar 5 Tickets Aleatorios</button>
      </div>
      <table>
        <thead><tr><th>Ticket</th><th>OC</th><th>SKU</th><th>Escenario</th><th>Acción / Servo</th></tr></thead>
        <tbody id="tbl-tickets"></tbody>
      </table>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3>Lotes en Recepción (Conteo en Vivo)</h3>
      <table>
        <thead><tr><th>Lote</th><th>Proveedor</th><th>Producto</th><th>Color</th><th>Conteo</th><th>Estado</th></tr></thead>
        <tbody id="tbl-lotes"></tbody>
      </table>
    </div>

    <div class="card">
      <h3>Lecturas en Banda y Órdenes de Trabajo</h3>
      <table>
        <thead><tr><th>Caja</th><th>Color</th><th>Estado</th><th>Servo / Ruta</th><th>Hora</th></tr></thead>
        <tbody id="tbl-lecturas"></tbody>
      </table>
      <h3 style="margin-top:14px;">Órdenes de Trabajo Automáticas</h3>
      <table>
        <thead><tr><th>ID</th><th>Lote</th><th>Descripción</th><th>Estado</th></tr></thead>
        <tbody id="tbl-ot"></tbody>
      </table>
    </div>
  </div>

  <script>
    let initializedSelects = false;

    async function refreshDashboard() {
      const res = await fetch('/api/dashboard');
      const data = await res.json();

      document.getElementById('last-event').textContent = data.session.last_event;
      document.getElementById('badge-conteo').textContent = 'CONTEO: ' + data.session.conteo_actual;
      document.getElementById('badge-servo').textContent = 'SERVO: ' + data.session.servo_activado;
      document.getElementById('live-color').textContent = data.vision_live.detected_color;

      if (!initializedSelects && data.lotes.length > 0) {
        const selLote = document.getElementById('sel-lote');
        selLote.innerHTML = data.lotes.map(l => `<option value="${l.ID_LOTE}">Lote #${l.ID_LOTE} (OC #${l.ID_OC} - ${l.NOMBRE_PRODUCTO} / ${l.NOMBRE_COLOR})</option>`).join('');
        const selColor = document.getElementById('ins-color');
        selColor.innerHTML = data.colores.map(c => `<option value="${c.ID_COLOR_PRODUCTO}">${c.NOMBRE_COLOR} — ${c.NOMBRE_PRODUCTO}</option>`).join('');
        initializedSelects = true;
      }

      document.getElementById('tbl-lotes').innerHTML = data.lotes.map(l =>
        `<tr><td>#${l.ID_LOTE}</td><td>${l.NOMBRE_PROVEEDOR}</td><td>${l.NOMBRE_PRODUCTO}</td><td><span style="color:${l.CODIGO_HEX};font-weight:bold;">${l.NOMBRE_COLOR}</span></td><td><b>${l.CANTIDAD_CAJAS_CONTADA} / ${l.CANTIDAD_CAJAS_ESPERADA}</b></td><td>${l.NOMBRE_ESTADO_LOTE}</td></tr>`
      ).join('');

      document.getElementById('tbl-lecturas').innerHTML = data.lecturas.map(r =>
        `<tr><td>${r.CODIGO_CAJA}</td><td>${r.COLOR_DETECTADO}</td><td>${r.ESTADO_INSPECCION}</td><td><b>${r.RUTA_ACCIONADA}</b></td><td>${r.TIMESTAMP_LECTURA.split(' ')[1]}</td></tr>`
      ).join('');

      document.getElementById('tbl-ot').innerHTML = data.ordenes_trabajo.map(o =>
        `<tr><td>#${o.ID_OT}</td><td>Lote ${o.ID_LOTE}</td><td>${o.DESCRIPCION}</td><td>${o.NOMBRE_ESTADO_ORDEN_TRABAJO}</td></tr>`
      ).join('');

      document.getElementById('tbl-tickets').innerHTML = data.tickets.map(t =>
        `<tr><td>${t.TICKET_ID}</td><td>${t.PO_ID}</td><td>${t.SKU}</td><td>${t.SCENARIO}</td><td>${t.RECOMMENDED_ACTION}</td></tr>`
      ).join('');
    }

    async function updateConfig() {
      await fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          id_lote: parseInt(document.getElementById('sel-lote').value),
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
          id_lote: parseInt(document.getElementById('sel-lote').value),
          id_color_producto: parseInt(document.getElementById('ins-color').value),
          estado_inspeccion: document.getElementById('ins-estado').value,
          cantidad_real: parseInt(document.getElementById('ins-cant').value)
        })
      });
      const d = await res.json();
      document.getElementById('qr-box').style.display = 'flex';
      document.getElementById('qr-img').src = 'data:image/png;base64,' + d.qr_base64;
      document.getElementById('qr-info').innerHTML = `<b>Código:</b> ${d.codigo_caja}<br><b>Producto:</b> ${d.producto} (${d.color})<br><b>Estado:</b> ${d.estado}<br><b>Acción Servo:</b> ${d.ruta}`;
    }

    async function generarTickets(n) {
      await fetch('/api/tickets/random?cantidad=' + n, { method: 'POST' });
      refreshDashboard();
    }

    async function simularPaso(color, qr = '') {
      await fetch(`/api/simular_paso_banda?color=${color}&qr=${encodeURIComponent(qr)}`, { method: 'POST' });
      refreshDashboard();
    }

    async function resetDemo() {
      await fetch('/api/reset_demo', { method: 'POST' });
      refreshDashboard();
    }

    setInterval(refreshDashboard, 1200);
    refreshDashboard();
  </script>
</body>
</html>
'''
}


def main():
    print("[1/3] Generando estructura completa de CEDIS IoT...")
    os.makedirs(os.path.join(PROJECT_DIR, "static"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "data"), exist_ok=True)

    for rel_path, content in FILES.items():
        full_path = os.path.join(PROJECT_DIR, rel_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   -> Escrito: {full_path}")

    print("\n[2/3] Instalando dependencias compatibles con Python 3.13+...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "opencv-python", "numpy", "qrcode", "pillow"]
    )

    print("\n[3/3] Levantando servidor CEDIS IoT en http://127.0.0.1:8000 ...")
    subprocess.check_call(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=PROJECT_DIR,
    )


if __name__ == "__main__":
    main()