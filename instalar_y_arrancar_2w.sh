#!/usr/bin/env bash
set -e

echo "=== INSTALADOR CEDIS IoT FINAL v2 - ORANGE PI ZERO 2W ==="

echo "[1/4] Instalando dependencias del sistema, OpenCV y PySerial..."
apt-get update -qq
apt-get install -y -qq python3-opencv python3-numpy python3-pil python3-pymysql python3-fastapi python3-uvicorn python3-serial fonts-dejavu-core >/dev/null 2>&1 || true
pip install --break-system-packages -q fastapi uvicorn pymysql pillow qrcode pyserial opencv-python-headless numpy 2>/dev/null || pip install --break-system-packages -q fastapi uvicorn pymysql pillow qrcode pyserial

echo "[2/4] Verificando MariaDB y usuario app_user..."
systemctl start mariadb 2>/dev/null || true
mariadb -e "CREATE DATABASE IF NOT EXISTS trisomicos_bd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mariadb -e "DROP USER IF EXISTS 'app_user'@'localhost'; CREATE USER 'app_user'@'localhost' IDENTIFIED BY 'Almacen2026!'; GRANT ALL PRIVILEGES ON trisomicos_bd.* TO 'app_user'@'localhost'; FLUSH PRIVILEGES;"

if [ -f "/root/trisomicos_bd.sql" ]; then
    TABLAS=$(mariadb -N -s -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='trisomicos_bd';")
    if [ "$TABLAS" -lt "10" ]; then
        echo "   -> Importando /root/trisomicos_bd.sql ..."
        mariadb trisomicos_bd < /root/trisomicos_bd.sql
    fi
fi

echo "[3/4] Preparando /root/Downloads/app_zero2w_final.py ..."
mkdir -p /root/Downloads
if [ -f "./app_zero2w_final.py" ] && [ "$(realpath ./app_zero2w_final.py)" != "/root/Downloads/app_zero2w_final.py" ]; then
    cp ./app_zero2w_final.py /root/Downloads/app_zero2w_final.py
fi
sed -i 's/\r$//' /root/Downloads/app_zero2w_final.py

echo "[4/4] Arrancando servidor unificado en http://0.0.0.0:8000 ..."
cd /root/Downloads
exec uvicorn app_zero2w_final:app --host 0.0.0.0 --port 8000
