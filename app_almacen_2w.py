import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel
import pymysql

app = FastAPI(title="Zero 2W - Tickets & Validador trisomicos_bd")

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "app_user",
    "password": "Almacen2026!",
    "database": "trisomicos_bd",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

OUTPUT_DIR = "tickets_generados"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CATALOGO_SKUS = [
    {"sku": "TORN-M6X20", "desc": "Tornillo Hexagonal M6x20 Acero", "unit": "pcs", "cost": 1.50, "wo": "OT-LOTE", "zone": "RACK-A1", "oc_id": 1, "lote_id": 1},
    {"sku": "ROD-608ZZ", "desc": "Rodamiento Rigido Bolas 608ZZ", "unit": "pcs", "cost": 28.00, "wo": "OT-LOTE", "zone": "RACK-B3", "oc_id": 2, "lote_id": 2},
    {"sku": "CABLE-18AWG", "desc": "Cable Industrial Calibre 18 AWG", "unit": "m", "cost": 6.20, "wo": "OT-LOTE", "zone": "RACK-C2", "oc_id": 3, "lote_id": 3},
    {"sku": "SENSOR-IND-M12", "desc": "Sensor Inductivo PNP M12 4mm", "unit": "pcs", "cost": 145.00, "wo": "OT-LOTE", "zone": "RACK-A4", "oc_id": 4, "lote_id": 4},
]

PROVEEDORES = ["PROV-NORTE S.A.", "PROV-GOLFO IND.", "SUMINISTROS VERACRUZ"]


def norm_sku(val: Optional[str]) -> str:
    return (val or "").strip().upper().replace("-", "_")


def get_conn():
    return pymysql.connect(**DB_CONFIG)


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


def generar_datos_ticket(indice: int, escenario_forzado: Optional[str] = None, oc_id: Optional[int] = None) -> Dict:
    item = random.choice(CATALOGO_SKUS)
    if oc_id is not None:
        match = next((x for x in CATALOGO_SKUS if x["oc_id"] == oc_id), None)
        if match:
            item = match

    ordered_qty = random.choice([20, 50, 100, 150, 200])
    escenarios = ["COINCIDE", "DIFIERE_PARCIAL", "DIFIERE_EXCEDENTE", "DIFIERE_NO_CUADRA_FISICO", "INCOMPLETO"]
    escenario = escenario_forzado or random.choice(escenarios)

    received_qty = ordered_qty
    measured_qty = ordered_qty
    unit_cost = item["cost"]
    lot_id = item["lote_id"]
    status = "COINCIDE"
    action = "APROBAR RECEPCION Y SURTIR OT"

    if escenario == "DIFIERE_PARCIAL":
        diff = max(1, int(ordered_qty * random.uniform(0.10, 0.35)))
        received_qty = ordered_qty - diff
        measured_qty = received_qty
        status = "DIFIERE_PARCIAL"
        action = "RECLAMAR FALTANTE Y AJUSTAR OT"
    elif escenario == "DIFIERE_EXCEDENTE":
        diff = max(1, int(ordered_qty * random.uniform(0.10, 0.30)))
        received_qty = ordered_qty + diff
        measured_qty = received_qty
        status = "DIFIERE_EXCEDENTE"
        action = "ENVIAR EXCEDENTE A CUARENTENA"
    elif escenario == "DIFIERE_NO_CUADRA_FISICO":
        received_qty = ordered_qty
        delta_fisico = random.choice([-1, 1]) * max(1, int(ordered_qty * random.uniform(0.15, 0.40)))
        measured_qty = max(0, received_qty + delta_fisico)
        status = "DIFIERE_NO_CUADRA_FISICO"
        action = "BLOQUEAR SALDO Y DISPARAR RECONTEO"
    elif escenario == "INCOMPLETO":
        unit_cost = None
        status = "INCOMPLETO"
        action = "AISLAR REGISTRO (FALTA COSTO)"

    delta_vs_order = (measured_qty - ordered_qty) if status == "DIFIERE_NO_CUADRA_FISICO" else (received_qty - ordered_qty)

    return {
        "ticket_id": f"TCK-2026-{indice:04d}",
        "oc_id": item["oc_id"],
        "lote_id": lot_id,
        "po_id": f"OC-{item['oc_id']:04d}",
        "supplier": random.choice(PROVEEDORES),
        "sku": item["sku"],
        "desc": item["desc"],
        "zone": item["zone"],
        "unit": item["unit"],
        "ordered_qty": ordered_qty,
        "received_qty": received_qty,
        "measured_qty": measured_qty,
        "delta_vs_order": delta_vs_order,
        "unit_cost_mxn": unit_cost,
        "lot": f"LOTE-{lot_id:03d}",
        "status": status,
        "recommended_action": action,
        "linked_wo": item["wo"],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def render_ticket_image(ticket: Dict) -> Image.Image:
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


def validar_ticket_en_bd(ticket: Dict, crear_ot: bool = False) -> Dict:
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
                    observaciones.append(
                        f"Cantidad pedida en ticket ({ticket.get('ordered_qty')}) difiere del calculo OC ({oc_row['OC_CAJAS']} cajas x {oc_row['PIEZAS_POR_CAJA']} = {unidades_esperadas_bd})."
                    )

            if ticket.get("status") != "COINCIDE":
                coincide_bd = False
                observaciones.append(f"Dictamen de ticket: {ticket.get('status')} ({ticket.get('recommended_action')}).")

            if ticket.get("unit_cost_mxn") is None:
                coincide_bd = False
                observaciones.append("Falta costo unitario (unit_cost_mxn es NULL).")

            ot_generada_id = None
            if crear_ot and not coincide_bd and lote_row:
                tipo_inc = 1
                if ticket.get("status") == "DIFIERE_PARCIAL" or (ticket.get("delta_vs_order") or 0) < 0:
                    tipo_inc = 3
                elif ticket.get("status") == "DIFIERE_EXCEDENTE" or (ticket.get("delta_vs_order") or 0) > 0:
                    tipo_inc = 4
                elif ticket.get("status") == "DIFIERE_NO_CUADRA_FISICO":
                    tipo_inc = 1

                cur.execute(
                    """
                    INSERT INTO orden_trabajo
                        (ID_TIPO_INCIDENCIA, ID_ESTADO_ORDEN_TRABAJO, ID_LOTE, ID_CAJA, FECHA_GENERACION)
                    VALUES (%s, 1, %s, NULL, NOW())
                    """,
                    (tipo_inc, lote_row["ID_LOTE"]),
                )
                conn.commit()
                ot_generada_id = cur.lastrowid

    return {
        "validacion_bd": "COINCIDE_CON_BD" if coincide_bd else "DIFIERE_O_REQUIERE_REVISION",
        "coincide_bd": coincide_bd,
        "observaciones": observaciones if observaciones else ["Todos los campos coinciden con trisomicos_bd."],
        "oc_bd": oc_row,
        "lote_bd": lote_row,
        "ot_generada_id": ot_generada_id,
    }


class GenerarRequest(BaseModel):
    cantidad: int = 4
    formato: str = "jpg_y_pdf"
    escenario: Optional[str] = None
    oc_id: Optional[int] = None
    validar_bd: bool = True
    crear_ot_en_falla: bool = False


class ValidarTicketRequest(BaseModel):
    ticket: Dict[str, Any]
    crear_ot: bool = False


class LecturaSensorRequest(BaseModel):
    source_node: str
    id_caja: Optional[int] = None
    resultado: str = "OK"


class ComandoPi4Request(BaseModel):
    command: str
    id_oc: Optional[int] = None
    id_lote: Optional[int] = None


@app.post("/api/tickets/generar")
def api_generar_tickets(req: GenerarRequest):
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
            img.save(os.path.join(OUTPUT_DIR, jpg_name), "JPEG", quality=92)
            t["jpg_url"] = f"/api/tickets/archivo/{jpg_name}"
        else:
            t["jpg_url"] = None

        if req.validar_bd:
            try:
                t["validacion"] = validar_ticket_en_bd(t, crear_ot=req.crear_ot_en_falla)
            except Exception as exc:
                t["validacion"] = {"validacion_bd": "ERROR_BD", "coincide_bd": False, "observaciones": [str(exc)]}

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
        return {"error": "Archivo no encontrado"}
    return FileResponse(path, filename=safe_name)


@app.post("/api/tickets/validar")
def api_validar_ticket(req: ValidarTicketRequest):
    return validar_ticket_en_bd(req.ticket, crear_ot=req.crear_ot)


@app.get("/api/bd/resumen")
def api_bd_resumen():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT oc.ID_OC, p.NOMBRE_PROVEEDOR, eoc.NOMBRE_ESTADO_OC,
                       pr.NOMBRE_PRODUCTO, ocd.CANTIDAD_CAJAS_ESPERADA, ocd.PIEZAS_POR_CAJA
                FROM orden_compra oc
                JOIN proveedor p ON oc.ID_PROVEEDOR = p.ID_PROVEEDOR
                JOIN estado_oc eoc ON oc.ID_ESTADO_OC = eoc.ID_ESTADO_OC
                JOIN orden_compra_detalle ocd ON oc.ID_OC = ocd.ID_OC
                JOIN producto pr ON ocd.ID_PRODUCTO = pr.ID_PRODUCTO
                ORDER BY oc.ID_OC
                """
            )
            ocs = cur.fetchall()

            cur.execute(
                """
                SELECT lr.ID_LOTE, lr.ID_OC, lr.CANTIDAD_CAJAS_ESPERADA,
                       lr.CANTIDAD_CAJAS_CONTADA, el.NOMBRE_ESTADO_LOTE
                FROM lote_recepcion lr
                JOIN estado_lote el ON lr.ID_ESTADO_LOTE = el.ID_ESTADO_LOTE
                ORDER BY lr.ID_LOTE
                """
            )
            lotes = cur.fetchall()

            cur.execute(
                """
                SELECT ot.ID_ORDEN_TRABAJO, ti.NOMBRE_TIPO_INCIDENCIA,
                       eot.NOMBRE_ESTADO_ORDEN_TRABAJO, ot.ID_LOTE, ot.FECHA_GENERACION
                FROM orden_trabajo ot
                JOIN tipo_incidencia ti ON ot.ID_TIPO_INCIDENCIA = ti.ID_TIPO_INCIDENCIA
                JOIN estado_orden_trabajo eot ON ot.ID_ESTADO_ORDEN_TRABAJO = eot.ID_ESTADO_ORDEN_TRABAJO
                ORDER BY ot.ID_ORDEN_TRABAJO DESC LIMIT 20
                """
            )
            ots = cur.fetchall()

            cur.execute("SELECT ID_LECTURA, ID_CAJA, TIMESTAMP_LECTURA, RESULTADO FROM lectura_banda ORDER BY ID_LECTURA DESC LIMIT 15")
            lecturas = cur.fetchall()

    for r in ots:
        if r.get("FECHA_GENERACION"):
            r["FECHA_GENERACION"] = str(r["FECHA_GENERACION"])
    for r in lecturas:
        if r.get("TIMESTAMP_LECTURA"):
            r["TIMESTAMP_LECTURA"] = str(r["TIMESTAMP_LECTURA"])

    return {"ordenes_compra": ocs, "lotes_recepcion": lotes, "ordenes_trabajo": ots, "lecturas_banda": lecturas}


@app.post("/api/v1/sensor")
def api_sensor_esp32(ev: LecturaSensorRequest):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if ev.id_caja:
                cur.execute(
                    "INSERT INTO lectura_banda (ID_CAJA, TIMESTAMP_LECTURA, RESULTADO) VALUES (%s, NOW(), %s)",
                    (ev.id_caja, ev.resultado[:10]),
                )
        conn.commit()
    return {"ok": True, "source_node": ev.source_node, "resultado": ev.resultado}


@app.post("/api/v1/commands")
def api_comando_pi4(cmd: ComandoPi4Request):
    if cmd.command == "CONSULTAR_OC" and cmd.id_oc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM orden_compra_detalle WHERE ID_OC = %s", (cmd.id_oc,))
                rows = cur.fetchall()
        return {"ok": True, "command": cmd.command, "detalle_oc": rows}
    return {"ok": True, "command": cmd.command}


HTML_UI = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Zero 2W — Tickets & trisomicos_bd</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    header { background: #1e293b; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }
    h2 { margin: 0 0 12px 0; font-size: 18px; color: #38bdf8; }
    label { display: block; font-size: 13px; margin-top: 8px; color: #cbd5e1; }
    select, input, button { margin-top: 4px; padding: 8px 10px; border-radius: 6px; border: 1px solid #475569; background: #0f172a; color: #f8fafc; }
    button { background: #0284c7; border: none; font-weight: 600; cursor: pointer; margin-right: 6px; margin-top: 12px; }
    button:hover { background: #0369a1; }
    .ticket-box { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin-top: 12px; }
    .ok { color: #4ade80; font-weight: 700; }
    .err { color: #f87171; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
    th, td { border-bottom: 1px solid #334155; padding: 6px 8px; text-align: left; }
    th { color: #94a3b8; }
    img.preview { max-width: 240px; border-radius: 6px; border: 1px solid #475569; margin-top: 8px; }
    a { color: #7dd3fc; }
  </style>
</head>
<body>
<header>
  <div><strong>ALMACEN IOT · ZERO 2W</strong> — Generador de Tickets y Validador <code>trisomicos_bd</code></div>
  <button onclick="cargarBD()">Actualizar BD</button>
</header>

<div class="grid">
  <div class="card">
    <h2>1. Generador de Tickets (JPG / PDF) + Validacion BD</h2>
    <label>Cantidad de tickets:
      <input id="cant" type="number" min="1" max="15" value="2"/>
    </label>
    <label>Formato de salida:
      <select id="formato">
        <option value="jpg_y_pdf">JPG + PDF</option>
        <option value="jpg">Solo JPG</option>
        <option value="pdf">Solo PDF</option>
      </select>
    </label>
    <label>Escenario:
      <select id="escenario">
        <option value="">Aleatorio</option>
        <option value="COINCIDE">COINCIDE</option>
        <option value="DIFIERE_PARCIAL">DIFIERE_PARCIAL</option>
        <option value="DIFIERE_EXCEDENTE">DIFIERE_EXCEDENTE</option>
        <option value="DIFIERE_NO_CUADRA_FISICO">DIFIERE_NO_CUADRA_FISICO</option>
        <option value="INCOMPLETO">INCOMPLETO</option>
      </select>
    </label>
    <label>OC vinculada en BD:
      <select id="oc_id">
        <option value="">Aleatoria (1 a 4)</option>
        <option value="1">OC-0001 (TORN_M6X20)</option>
        <option value="2">OC-0002 (ROD_608ZZ)</option>
        <option value="3">OC-0003 (CABLE_18AWG)</option>
        <option value="4">OC-0004 (SENSOR_IND_M12)</option>
      </select>
    </label>
    <label><input id="crear_ot" type="checkbox"/> Registrar incidencia en <code>orden_trabajo</code> si difiere</label>
    <button onclick="generarTickets()">Generar y Validar</button>
    <div id="pdf_link" style="margin-top:8px;"></div>
    <div id="resultados_tickets"></div>
  </div>

  <div class="card">
    <h2>2. Visualizador de Base de Datos (<code>trisomicos_bd</code>)</h2>
    <div id="bd_status" style="font-size:13px; color:#94a3b8;">Cargando...</div>
    <h3 style="font-size:15px; margin:12px 0 4px 0;">Ordenes de Compra y Detalle</h3>
    <div id="tbl_oc"></div>
    <h3 style="font-size:15px; margin:14px 0 4px 0;">Lotes de Recepcion</h3>
    <div id="tbl_lotes"></div>
    <h3 style="font-size:15px; margin:14px 0 4px 0;">Ordenes de Trabajo (Incidencias)</h3>
    <div id="tbl_ots"></div>
  </div>
</div>

<script>
async function generarTickets() {
  const payload = {
    cantidad: parseInt(document.getElementById("cant").value || "1", 10),
    formato: document.getElementById("formato").value,
    escenario: document.getElementById("escenario").value || null,
    oc_id: document.getElementById("oc_id").value ? parseInt(document.getElementById("oc_id").value, 10) : null,
    validar_bd: true,
    crear_ot_en_falla: document.getElementById("crear_ot").checked
  };
  const res = await fetch("/api/tickets/generar", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  document.getElementById("pdf_link").innerHTML = data.pdf_url
    ? `PDF generado: <a href="${data.pdf_url}" target="_blank">Descargar PDF</a>` : "";

  const cont = document.getElementById("resultados_tickets");
  cont.innerHTML = "";
  (data.tickets || []).forEach(t => {
    const v = t.validacion || {};
    const cls = v.coincide_bd ? "ok" : "err";
    const obs = (v.observaciones || []).map(o => `<li>${o}</li>`).join("");
    cont.innerHTML += `
      <div class="ticket-box">
        <div><strong>${t.ticket_id}</strong> · ${t.po_id} · <code>${t.sku}</code> · Ped: ${t.ordered_qty} / Rec: ${t.received_qty} / Sensor: ${t.measured_qty}</div>
        <div class="${cls}" style="margin-top:4px;">BD: ${v.validacion_bd || ""} ${v.ot_generada_id ? "· OT #" + v.ot_generada_id : ""}</div>
        <ul style="margin:6px 0 0 18px; font-size:13px;">${obs}</ul>
        ${t.jpg_url ? `<div><img class="preview" src="${t.jpg_url}"/><br/><a href="${t.jpg_url}" target="_blank">Abrir JPG</a></div>` : ""}
      </div>`;
  });
  cargarBD();
}

function renderTable(rows, cols) {
  if (!rows || !rows.length) return "<div style='font-size:13px;color:#94a3b8;'>Sin registros</div>";
  const ths = cols.map(c => `<th>${c}</th>`).join("");
  const trs = rows.map(r => `<tr>${cols.map(c => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
}

async function cargarBD() {
  try {
    const res = await fetch("/api/bd/resumen");
    if (!res.ok) {
      const txt = await res.text();
      document.getElementById("bd_status").innerHTML = "<span class='err'>Error HTTP " + res.status + ": " + txt + "</span>";
      return;
    }
    const d = await res.json();
    document.getElementById("bd_status").innerHTML = "<span class='ok'>Conectado a trisomicos_bd</span>";
    document.getElementById("tbl_oc").innerHTML = renderTable(d.ordenes_compra, ["ID_OC", "NOMBRE_PROVEEDOR", "NOMBRE_PRODUCTO", "CANTIDAD_CAJAS_ESPERADA", "PIEZAS_POR_CAJA"]);
    document.getElementById("tbl_lotes").innerHTML = renderTable(d.lotes_recepcion, ["ID_LOTE", "ID_OC", "CANTIDAD_CAJAS_ESPERADA", "CANTIDAD_CAJAS_CONTADA", "NOMBRE_ESTADO_LOTE"]);
    document.getElementById("tbl_ots").innerHTML = renderTable(d.ordenes_trabajo, ["ID_ORDEN_TRABAJO", "NOMBRE_TIPO_INCIDENCIA", "NOMBRE_ESTADO_ORDEN_TRABAJO", "ID_LOTE"]);
  } catch (e) {
    document.getElementById("bd_status").innerHTML = "<span class='err'>Error al consultar BD: " + e + "</span>";
  }
}
cargarBD();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_UI
