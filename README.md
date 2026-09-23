# 🎥 AscendMxVision - Detección de Personas con YOLOv11 en Huawei Ascend

Sistema de visión por computadora que detecta personas en video, cuenta cuántas entran a una zona definida y cuántas cruzan una línea horizontal. Corre sobre hardware **Huawei Ascend** usando el SDK **MindX (mxVision)** para inferencia acelerada en NPU.

---

## 🧠 ¿Qué hace este proyecto?

1. **Lee un video** (archivo o stream RTSP en tiempo real)
2. **Detecta personas** usando el modelo YOLOv11 (convertido a formato `.om` para Ascend)
3. **Asigna un ID** a cada persona (tracking básico por distancia)
4. **Cuenta personas** que entran a una zona rectangular (verde)
5. **Detecta cruces** de una línea horizontal (roja)
6. **Genera un video de salida** con las detecciones dibujadas

---

## 📁 Estructura del Proyecto

```
AscendMxVision_Jessica/
├── config/
│   ├── coco.names                        # Nombres de clases COCO (80 clases)
│   ├── pipeline.json                     # Configuración del pipeline MxVision (referencia)
│   └── zones.json                        # Coordenadas de zona y línea de detección
├── models/
│   ├── yolo11n.pt                        # Modelo original PyTorch
│   ├── yolo11n.onnx                      # Modelo exportado a ONNX
│   ├── yolov11.om                        # Modelo convertido para Ascend (batch 1)
│   └── yolov11_bs8_rgb.om               # Modelo para Ascend (batch 8) ← SE USA
├── utils/
│   └── zone_analyzer.py                  # Clase auxiliar para análisis de zonas
├── videos/
│   └── videotest.mp4                     # Video de prueba
├── pipeline_1M_B8.py                     # Pipeline base (batch 8)
├── pipeline_con_profiler.py              # Pipeline con optimización INTER_NEAREST
├── pipeline_con_estadisticas1M_B8.py     # Pipeline ultra-rápido con profiler
└── pipeline_stream_mediamtx.py           # Pipeline RTSP en tiempo real (MediaMTX)
```

---

## 🔧 Requisitos

| Requisito | Detalle |
|-----------|---------|
| Hardware | Huawei Atlas (con NPU Ascend) |
| SDK | MindX mxVision 7.3.0 |
| Python | 3.7+ |
| Librerías | numpy, opencv-python (cv2) |
| Modelo | YOLOv11n convertido a `.om` con batch_size=8 |
| MediaMTX | (solo para streams) [github.com/bluenviron/mediamtx](https://github.com/bluenviron/mediamtx) |

---

## ⚙️ Configuración

El archivo `config/zones.json` define dónde buscar personas:

```json
{
    "zona_rectangular": {
        "x1": 400, "y1": 500,
        "x2": 800, "y2": 700
    },
    "linea_horizontal": {
        "y": 450
    }
}
```

- **zona_rectangular**: Si los pies de una persona caen dentro de este rectángulo → se cuenta como "entrada a zona"
- **linea_horizontal**: Si los pies cruzan esta coordenada Y de arriba hacia abajo → se registra un "cruce de línea"

---

## 🚀 Cómo Ejecutar

### Pipeline básico (video archivo)
```bash
python pipeline_1M_B8.py
```

### Pipeline optimizado (más rápido)
```bash
python pipeline_con_profiler.py
```

### Pipeline con estadísticas de rendimiento
```bash
python pipeline_con_estadisticas1M_B8.py
```

### Pipeline en tiempo real con cámaras RTSP (MediaMTX)
```bash
# 1. Levantar MediaMTX con las cámaras configuradas
./mediamtx

# 2. Ejecutar el pipeline
python pipeline_stream_mediamtx.py
```

> ⚠️ Los paths del video y modelo están al final de cada script en `if __name__ == "__main__"`. Edítalos según tu entorno.

---

## 📖 Paso a Paso (Dummy Style)

### Paso 1: Se carga el modelo en la NPU
```
El modelo YOLOv11 (archivo .om) se sube a la tarjeta Ascend.
Piensa en esto como "instalar la app de detección en el chip especial".
```

### Paso 2: Se lee el video
```
- Modo archivo: Se carga todo el video en memoria (todas las fotos en una pila).
- Modo stream: Se lee frame a frame en tiempo real desde las cámaras.
```

### Paso 3: Se procesan frames en lotes de 8 (batches)
```
En vez de analizar 1 foto a la vez, le mandamos 8 fotos juntas a la NPU.
Es más eficiente, como lavar 8 platos a la vez en lugar de 1.
```

### Paso 4: Se preprocesa cada frame
```
Cada foto se achica a 640x640 pixeles (el tamaño que el modelo espera).
Es como recortar una foto para que quepa en un marco específico.
```

### Paso 5: Se manda el batch a la NPU para inferencia
```
Las 8 fotos preparadas se envían al chip Ascend.
El chip analiza las fotos y dice: "Aquí hay una persona en esta posición".
```

### Paso 6: Se decodifican los resultados
```
La NPU devuelve números crudos. Aquí los convertimos en:
- Coordenadas de la caja (bounding box) de cada persona
- Nivel de confianza (qué tan seguro está el modelo)
```

### Paso 7: Se aplica NMS (Non-Maximum Suppression)
```
A veces el modelo detecta la misma persona 3 veces.
NMS elimina las cajas duplicadas y se queda solo con la mejor.
Es como borrar fotos repetidas del álbum.
```

### Paso 8: Se asigna un ID a cada persona (tracking)
```
Se compara la posición de cada persona con las del frame anterior.
Si alguien está cerca de donde estaba antes → es la misma persona → mismo ID.
Si nadie coincide → es una persona nueva → nuevo ID.
```

### Paso 9: Se analiza zona y línea
```
- Si los PIES de la persona están dentro del rectángulo verde → CONTADA
- Si los pies CRUZAN la línea roja (de arriba a abajo) → CRUCE DETECTADO
```

### Paso 10: Se dibuja todo en el frame
```
Se pinta:
- Rectángulo verde semitransparente (zona)
- Línea roja horizontal
- Cajas de colores alrededor de cada persona con su ID
- Contador de personas
```

### Paso 11: Se guarda el video de salida
```
Todos los frames con las anotaciones se escriben en un nuevo archivo .mp4
(En modo stream esto es opcional)
```

---

## 📊 Diferencias entre los Scripts

| Script | Velocidad | Modo | Características |
|--------|-----------|------|-----------------|
| `pipeline_1M_B8.py` | ~16 FPS | Archivo | Básico, funcional |
| `pipeline_con_profiler.py` | ~20+ FPS | Archivo | Usa INTER_NEAREST (resize rápido) |
| `pipeline_con_estadisticas1M_B8.py` | ~20+ FPS | Archivo | Sin conversión BGR→RGB + profiler |
| `pipeline_stream_mediamtx.py` | Tiempo real | RTSP | Multi-cámara, reconexión automática |

---

## 📡 Configuración de MediaMTX (para streams)

### mediamtx.yml
```yaml
paths:
  cam1:
    source: rtsp://usuario:password@192.168.1.100:554/stream1
  cam2:
    source: rtsp://usuario:password@192.168.1.101:554/stream1
```

Esto expone las cámaras como `rtsp://localhost:8554/cam1`, `rtsp://localhost:8554/cam2`, etc.

### En el script, edita el dict STREAMS:
```python
STREAMS = {
    "cam1": "rtsp://localhost:8554/cam1",
    "cam2": "rtsp://localhost:8554/cam2",
}
```

---

## 🏗️ Flujo del Pipeline (Diagrama)

```
┌──────────┐    ┌──────────────┐    ┌───────────┐    ┌──────────────┐
│  Video / │───▶│ Resize 640x640│───▶│  NPU      │───▶│ Decodificar  │
│  Stream  │    │ (preproceso) │    │ Inferencia│    │  resultados  │
└──────────┘    └──────────────┘    └───────────┘    └──────┬───────┘
                                                            │
                                                            ▼
┌──────────┐    ┌──────────────┐    ┌───────────┐    ┌──────────────┐
│  Video / │◀───│   Dibujar    │◀───│  Análisis │◀───│     NMS +    │
│  Display │    │ anotaciones  │    │ zona/línea│    │   Tracking   │
└──────────┘    └──────────────┘    └───────────┘    └──────────────┘
```

### Arquitectura con MediaMTX

```
┌─────────┐     RTSP      ┌──────────┐     RTSP      ┌──────────────┐
│ Cámara 1│──────────────▶│          │──────────────▶│              │
├─────────┤               │ MediaMTX │               │   Pipeline   │
│ Cámara 2│──────────────▶│ (proxy)  │──────────────▶│   Ascend     │
├─────────┤               │          │               │   (NPU)      │
│ Cámara N│──────────────▶│          │──────────────▶│              │
└─────────┘               └──────────┘               └──────────────┘
                          localhost:8554              Batch de N cámaras
```

---

## 💡 Tips

- Para cambiar la zona de detección, edita `config/zones.json`
- El modelo espera imágenes de 640x640 en formato uint8
- El batch_size del modelo `.om` debe coincidir con el del script (8)
- Si quieres máxima velocidad sin video de salida, comenta `draw_frame` y `out.write`
- El tracking es básico (distancia euclidiana). Para algo más robusto considera DeepSORT o ByteTrack
- En modo stream, el pipeline descarta frames viejos automáticamente para mantener baja latencia
- Si una cámara se desconecta, se reconecta sola cada 3 segundos
