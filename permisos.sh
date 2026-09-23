echo "Cambiando permisos a 640 para archivos de Ascend..."

# Array con todos los archivos
archivos=(
    "/usr/local/Ascend/mxVision-7.3.0/lib/libmxbase.so"
    "/usr/local/Ascend/mindx/mxVision-7.3.0/lib/libmxbase.so"
    "/usr/local/Ascend/mindx/lib/libmxbase.so"
    "/usr/local/Ascend/mindx/mxVision-7.3.0/config/logging.conf"
    "/usr/local/Ascend/mindx/config/logging.conf"
    "/usr/local/Ascend/mxVision-7.3.0/config/logging.conf"
)

# Cambiar permisos de cada archivo
for archivo in "${archivos[@]}"; do
    if [ -f "$archivo" ]; then
        chmod 640 "$archivo"
        echo "✅ $archivo → 640"
    else
        echo "⚠️  Archivo no encontrado: $archivo"
    fi
done

echo "¡Completado!"
