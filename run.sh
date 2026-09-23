#!/bin/bash
# Script de inicio para el servicio

echo "🚀 Iniciando servicio de inferencia..."
echo "📂 Directorio: $(pwd)"

# Configurar variables de entorno
export MX_SDK_HOME=${MX_SDK_HOME:-/usr/local/Ascend/mxVision}
export LD_LIBRARY_PATH=$MX_SDK_HOME/lib:$LD_LIBRARY_PATH
export PYTHONPATH=$MX_SDK_HOME/python:$PYTHONPATH

echo "🔧 MX_SDK_HOME: $MX_SDK_HOME"

# Iniciar el servicio Flask en puerto 8080
python3 /opt/app/src/service.py
