# ======================================================
# Ascend 910B - CANN 8.5 + MindX 7.3 + OPS 910B
# ARM64 - Ubuntu 22.04 - VERSIÓN CON DEBUGGING DE MINDX
# ======================================================

FROM arm64v8/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# ------------------------------------------------------
# Dependencias base COMPLETAS
# ------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-dev python3-venv python3-pip \
        build-essential \
        ca-certificates \
        libglib2.0-0 \
        libsm6 libxext6 libxrender1 libxrender-dev \
        wget git \
        libgoogle-glog-dev \
        libgstreamer1.0-0 \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-plugins-base \
        gstreamer1.0-libav \
        gstreamer1.0-rtsp \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer-plugins-bad1.0-dev \
        libssl-dev \
        libopencv-dev \
        vim \
        tree \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/* \
        && rm -rf /tmp/*

# ------------------------------------------------------
# Variables de entorno base
# ------------------------------------------------------
ENV ASCEND_HOME=/usr/local/Ascend
ENV CANN_VERSION=8.5.0
ENV MINDX_HOME=$ASCEND_HOME/mindx

# ------------------------------------------------------
# Instalar CANN Toolkit 8.5
# ------------------------------------------------------
COPY libs/Ascend-cann-toolkit_8.5.0_linux-aarch64.run /tmp/
RUN chmod +x /tmp/Ascend-cann-toolkit_8.5.0_linux-aarch64.run && \
    /tmp/Ascend-cann-toolkit_8.5.0_linux-aarch64.run \
        --install --quiet --install-for-all --install-path=$ASCEND_HOME && \
    rm -f /tmp/Ascend-cann-toolkit_8.5.0_linux-aarch64.run

# ------------------------------------------------------
# Configurar entorno CANN
# ------------------------------------------------------
ENV LD_LIBRARY_PATH=$ASCEND_HOME/cann-$CANN_VERSION/lib64:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/opskernel:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/nnengine:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/dvpp:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/acl:\
$ASCEND_HOME/driver/lib64:\
$ASCEND_HOME/driver/lib64/common:\
$ASCEND_HOME/driver/lib64/driver:\
$LD_LIBRARY_PATH

ENV PATH=$ASCEND_HOME/cann-$CANN_VERSION/bin:$PATH
ENV ASCEND_OPP_PATH=$ASCEND_HOME/cann-$CANN_VERSION/opp
ENV ASCEND_AICPU_PATH=$ASCEND_HOME/cann-$CANN_VERSION
ENV PYTHONPATH=$ASCEND_HOME/cann-$CANN_VERSION/pyACL/python/site-packages/acl:$PYTHONPATH

# ------------------------------------------------------
# Instalar kernels 910B
# ------------------------------------------------------
COPY libs/Ascend-cann-910b-ops_8.5.0_linux-aarch64.run /tmp/
RUN chmod +x /tmp/Ascend-cann-910b-ops_8.5.0_linux-aarch64.run && \
    /tmp/Ascend-cann-910b-ops_8.5.0_linux-aarch64.run \
        --install --quiet --install-for-all --install-path=$ASCEND_HOME && \
    rm -f /tmp/Ascend-cann-910b-ops_8.5.0_linux-aarch64.run

# ------------------------------------------------------
# VERIFICAR CANN ANTES DE MINDX
# ------------------------------------------------------
RUN echo "=== VERIFICANDO CANN ===" && \
    ls -la $ASCEND_HOME/cann-$CANN_VERSION/lib64/ && \
    echo "Librerías CANN: $(ls $ASCEND_HOME/cann-$CANN_VERSION/lib64/*.so 2>/dev/null | wc -l) encontradas"

# ------------------------------------------------------
# DEBUGGING: Información del sistema antes de MindX
# ------------------------------------------------------
RUN echo "=== INFORMACIÓN DEL SISTEMA ===" && \
    uname -a && \
    cat /etc/os-release && \
    df -h && \
    free -h && \
    echo "=== VARIABLES DE ENTORNO ===" && \
    env | sort

# ------------------------------------------------------
# INSTALAR MINDX CON DEBUGGING EXTREMO
# ------------------------------------------------------
COPY libs/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run /tmp/

# Paso 1: Verificar el instalador
RUN echo "=== PASO 1: VERIFICANDO INSTALADOR ===" && \
    ls -la /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run && \
    file /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run || echo "file command not found" && \
    du -sh /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run && \
    md5sum /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run || echo "md5sum not available"

# Paso 2: Probar source del set_env.sh
RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    echo '=== PASO 2: SOURCE FUNCIONÓ ===' && \
    echo 'LD_LIBRARY_PATH='$LD_LIBRARY_PATH && \
    echo 'PATH='$PATH"

# Paso 3: Ver opciones del instalador
RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    chmod +x /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run && \
    echo '=== PASO 3: OPCIONES DEL INSTALADOR ===' && \
    /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --help"

# Paso 4: Intentar extraer el contenido
RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    cd /tmp && \
    echo '=== PASO 4: EXTRAYENDO CONTENIDO ===' && \
    ./Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --noexec --extract=mindx_extracted && \
    echo 'Contenido extraído:' && \
    ls -la mindx_extracted/ && \
    echo 'Total archivos: $(find mindx_extracted -type f | wc -l)'"

# Paso 5: Intentar instalación con diferentes métodos
RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    cd $ASCEND_HOME && \
    echo '=== PASO 5: INTENTO 1 - Instalación normal ===' && \
    /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --quiet --install --cann-path=$ASCEND_HOME && \
    echo '✅ Intento 1 completado' || echo '❌ Intento 1 falló'"

RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    cd $ASCEND_HOME && \
    echo '=== PASO 5: INTENTO 2 - Con install-path ===' && \
    /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --quiet --install --install-path=$ASCEND_HOME/mindx --cann-path=$ASCEND_HOME && \
    echo '✅ Intento 2 completado' || echo '❌ Intento 2 falló'"

RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    cd $ASCEND_HOME && \
    echo '=== PASO 5: INTENTO 3 - Sin quiet para ver errores ===' && \
    /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --install --cann-path=$ASCEND_HOME && \
    echo '✅ Intento 3 completado' || echo '❌ Intento 3 falló'"

RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    cd $ASCEND_HOME && \
    echo '=== PASO 5: INTENTO 4 - Con yes ===' && \
    yes | /tmp/Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --install --cann-path=$ASCEND_HOME && \
    echo '✅ Intento 4 completado' || echo '❌ Intento 4 falló'"

# Paso 6: Buscar MindX en el sistema
RUN echo "=== PASO 6: BUSCANDO MINDX EN EL SISTEMA ===" && \
    echo "Buscando en ASCEND_HOME:" && \
    find $ASCEND_HOME -name "*mindx*" -type d 2>/dev/null && \
    echo "Buscando en /usr/local:" && \
    find /usr/local -name "*mindx*" -type d 2>/dev/null && \
    echo "Buscando archivos .so relacionados:" && \
    find $ASCEND_HOME -name "*.so" | grep -i mindx || echo "No se encontraron .so"

# Paso 7: Extracción manual como fallback
RUN bash -c "source $ASCEND_HOME/cann-$CANN_VERSION/set_env.sh && \
    cd /tmp && \
    echo '=== PASO 7: EXTRACCIÓN MANUAL ===' && \
    rm -rf mindx_extracted && \
    ./Ascend-mindxsdk-mxvision_7.3.0_linux-aarch64.run --noexec --extract=mindx_extracted && \
    mkdir -p $ASCEND_HOME/mindx && \
    cp -r mindx_extracted/* $ASCEND_HOME/mindx/ && \
    rm -rf mindx_extracted && \
    echo '✅ Extracción manual completada'"

# Paso 8: Verificación final de MindX
RUN echo "=== PASO 8: VERIFICACIÓN FINAL ===" && \
    if [ -d "$ASCEND_HOME/mindx" ]; then \
        echo "✅ MindX directorio existe"; \
        echo "Contenido:"; \
        ls -la $ASCEND_HOME/mindx/ | head -30; \
        echo "Total elementos: $(ls $ASCEND_HOME/mindx/ | wc -l)"; \
        echo "Buscando libmxbase.so:"; \
        find $ASCEND_HOME/mindx -name "libmxbase.so" || echo "❌ libmxbase.so no encontrada"; \
        echo "Buscando StreamManagerApi:"; \
        find $ASCEND_HOME/mindx -name "*StreamManagerApi*" || echo "❌ StreamManagerApi no encontrado"; \
    else \
        echo "❌ MindX no se instaló"; \
        exit 1; \
    fi

# ------------------------------------------------------
# Crear symlinks
# ------------------------------------------------------
RUN mkdir -p $ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/dvpp \
             $ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/acl && \
    ln -sf $ASCEND_HOME/cann-$CANN_VERSION/lib64/libacl_vpss_mpi.so \
          $ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/dvpp/libacl_dvpp.so && \
    ln -sf $ASCEND_HOME/cann-$CANN_VERSION/lib64/libacl_vpss_mpi.so \
          $ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/dvpp/libacl_dvpp_mpi.so && \
    ln -sf $ASCEND_HOME/cann-$CANN_VERSION $ASCEND_HOME/ascend-toolkit/latest

# ------------------------------------------------------
# Variables de entorno completas
# ------------------------------------------------------
ENV LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/opskernel:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/nnengine:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/dvpp:\
$ASCEND_HOME/cann-$CANN_VERSION/lib64/plugin/acl:\
$ASCEND_HOME/driver/lib64:\
$ASCEND_HOME/driver/lib64/common:\
$ASCEND_HOME/driver/lib64/driver:\
$MINDX_HOME/opensource/lib:\
$MINDX_HOME/lib:\
$MINDX_HOME/lib/plugins:\
$MINDX_HOME/opensource/lib64:\
$LD_LIBRARY_PATH

ENV PATH=$ASCEND_HOME/cann-$CANN_VERSION/bin:\
$MINDX_HOME/bin:\
$MINDX_HOME/opensource/bin:\
$PATH

ENV ASCEND_VERSION=ascend-toolkit/latest
ENV ASCEND_OPP_PATH=$ASCEND_HOME/ascend-toolkit/latest/opp
ENV ASCEND_AICPU_PATH=$ASCEND_HOME/ascend-toolkit/latest
ENV ASCEND_CUSTOM_OPP_PATH=$ASCEND_HOME/cann-$CANN_VERSION/opp
ENV PYTHONPATH=$ASCEND_HOME/cann-$CANN_VERSION/pyACL/python/site-packages/acl:\
$MINDX_HOME/python:\
$PYTHONPATH

ENV MX_SDK_HOME=$MINDX_HOME
ENV MXSDK_OPENSOURCE_DIR=$MINDX_HOME/opensource
ENV GST_PLUGIN_SCANNER=$MINDX_HOME/opensource/libexec/gstreamer-1.0/gst-plugin-scanner
ENV GST_PLUGIN_PATH=$MINDX_HOME/opensource/lib/gstreamer-1.0:$MINDX_HOME/lib/plugins

# ======================================================
# 🚀 SECCIÓN MODIFICADA: CREACIÓN DE ma-user SEGÚN MODELARTS
# ======================================================

# ------------------------------------------------------
# 1. Crear usuario ma-user con UID=1000 y GID=100 (ma-group)
#    Siguiendo el estándar oficial de ModelArts
# ------------------------------------------------------
USER root

RUN default_user=$(getent passwd 1000 | awk -F ':' '{print $1}') || echo "uid: 1000 does not exist" && \
    default_group=$(getent group 100 | awk -F ':' '{print $1}') || echo "gid: 100 does not exist" && \
    if [ ! -z "${default_user}" ] && [ "${default_user}" != "ma-user" ]; then \
        userdel -r ${default_user}; \
    fi && \
    if [ ! -z "${default_group}" ] && [ "${default_group}" != "ma-group" ]; then \
        groupdel -f ${default_group}; \
    fi && \
    if ! getent group 100 > /dev/null; then \
        groupadd -g 100 ma-group; \
    fi && \
    useradd -d /home/ma-user -m -u 1000 -g 100 -s /bin/bash ma-user && \
    chmod -R 750 /home/ma-user

# ------------------------------------------------------
# 2. Configurar permisos de Ascend con 750 (estándar ModelArts)
# ------------------------------------------------------
RUN chmod -R 750 $MINDX_HOME 2>/dev/null || true && \
    chmod -R 750 $ASCEND_HOME/cann-$CANN_VERSION && \
    chmod -R 750 $ASCEND_HOME/driver 2>/dev/null || true && \
    chmod -R 750 $ASCEND_HOME/ascend-toolkit 2>/dev/null || true && \
    chown -R ma-user:ma-group $ASCEND_HOME 2>/dev/null || true

# Asegurar que ma-user sea propietario de su directorio home
RUN chown -R ma-user:ma-group /home/ma-user

# ------------------------------------------------------
# 3. Instalar sudo (opcional, pero sin NOPASSWD como antes)
# ------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends sudo && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# NOTA: NO se añade ma-user a sudoers con NOPASSWD
# ModelArts no lo requiere y puede ser un problema de seguridad

# ======================================================
# FIN DE SECCIÓN MODIFICADA
# ======================================================

# ------------------------------------------------------
# Configuración del entorno Python
# ------------------------------------------------------
USER ma-user
WORKDIR /home/ma-user

# Crear entorno virtual
RUN python3 -m venv /home/ma-user/ascend_env
ENV PATH=/home/ma-user/ascend_env/bin:$PATH

# Actualizar pip
RUN pip install --upgrade pip --no-cache-dir

# Instalar paquetes Python
RUN pip install --no-cache-dir \
        numpy==1.24.4 \
        pandas==2.0.3 \
        scipy==1.11.4 \
        opencv-python==4.9.0.80 \
        pillow==10.1.0 \
        matplotlib==3.7.5 \
        jupyterlab==4.0.11 \
        ipykernel==6.28.0 \
        ipython==8.18.1 \
        requests==2.31.0 \
        tqdm==4.66.1 && \
    pip cache purge

# Instalar wheel de MindX si existe
RUN if [ -f "$MINDX_HOME/python/mindx-7.3.0-py3-none-any.whl" ]; then \
        pip install $MINDX_HOME/python/mindx-7.3.0-py3-none-any.whl --no-cache-dir; \
    fi

# Registrar kernel
RUN python -m ipykernel install --user --name ascend_env \
        --display-name 'Python (Ascend 910B)'

# ------------------------------------------------------
# Copiar script de inicio
# ------------------------------------------------------
COPY --chown=ma-user:ma-group start-notebook.sh /home/ma-user/
RUN chmod +x /home/ma-user/start-notebook.sh

# ------------------------------------------------------
# Puerto
# ------------------------------------------------------
EXPOSE 8888
CMD ["/home/ma-user/start-notebook.sh"]

