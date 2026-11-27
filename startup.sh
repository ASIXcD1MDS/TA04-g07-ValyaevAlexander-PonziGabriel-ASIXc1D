#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  STARTUP - INSTALACIÓN DE DEPENDENCIAS (TA04-G07)"
echo "============================================================"

# Detectar comando de Python disponible
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] No se encontró Python instalado en el sistema."
    exit 1
fi

echo "[1/3] Actualizando pip..."
$PYTHON_CMD -m pip install --upgrade pip --quiet || true

echo "[2/3] Instalando librerías necesarias (requests, faker, qrcode, browser-cookie3)..."
$PYTHON_CMD -m pip install -r requirements.txt

echo "[3/3] Verificando importaciones..."
$PYTHON_CMD -c "
for pkg in ['requests', 'faker', 'qrcode', 'browser_cookie3']:
    try:
        __import__(pkg)
        print(f'  [OK] {pkg}')
    except ImportError as e:
        print(f'  [WARN] {pkg}: {e}')
"

echo "============================================================"
echo "  Entorno listo. Ya puedes ejecutar:"
echo "    $PYTHON_CMD src/procesar_xml.py"
echo "============================================================"
