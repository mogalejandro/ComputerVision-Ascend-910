#!/usr/bin/env python3
"""
Pipeline DEFINITIVO - batch_size=8 con modelo YOLOv11 en Huawei Ascend NPU.
Procesa un video archivo, detecta personas, las trackea y cuenta entradas a zona.
"""

import sys
import os
import json
import numpy as np
import cv2
import time

MX_SDK_HOME = os.environ.get('MX_SDK_HOME', os.path.expanduser('~/mxVision-7.3.0'))
sys.path.insert(0, os.path.join(MX_SDK_HOME, 'python'))

try:
    from mindx.sdk import base
    from mindx.sdk.base import Tensor, Model
    print("✅ mxVision cargado")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)


def nms(boxes, scores, iou_threshold=0.5):
    """
    Non-Maximum Suppression: elimina detecciones duplicadas.
    Cuando el modelo detecta la misma persona varias veces, NMS se queda
    solo con la caja de mayor confianza y descarta las que se solapan mucho.

    Args:
        boxes: lista de [x, y, w, h] de cada detección
        scores: lista de confianza de cada detección
        iou_threshold: umbral de solapamiento para considerar duplicado (0-1)

    Returns:
        Lista de índices de las detecciones que se conservan
    """
    if len(boxes) == 0:
        return []
    boxes_xyxy = []
    for box in boxes:
        x, y, w, h = box
        boxes_xyxy.append([x, y, x + w, y + h])
    boxes_xyxy = np.array(boxes_xyxy)
    scores = np.array(scores)
    indices = np.argsort(scores)[::-1]
    keep = []
    while len(indices) > 0:
        i = indices[0]
        keep.append(i)
        if len(indices) == 1:
            break
        xx1 = np.maximum(boxes_xyxy[i, 0], boxes_xyxy[indices[1:], 0])
        yy1 = np.maximum(boxes_xyxy[i, 1], boxes_xyxy[indices[1:], 1])
        xx2 = np.minimum(boxes_xyxy[i, 2], boxes_xyxy[indices[1:], 2])
        yy2 = np.minimum(boxes_xyxy[i, 3], boxes_xyxy[indices[1:], 3])
        w = np.maximum(0, xx2 - xx1)
        h = np.maximum(0, yy2 - yy1)
        intersection = w * h
        area_i = (boxes_xyxy[i, 2] - boxes_xyxy[i, 0]) * (boxes_xyxy[i, 3] - boxes_xyxy[i, 1])
        area_other = (boxes_xyxy[indices[1:], 2] - boxes_xyxy[indices[1:], 0]) * \
                     (boxes_xyxy[indices[1:], 3] - boxes_xyxy[indices[1:], 1])
        iou = intersection / (area_i + area_other - intersection + 1e-6)
        indices = indices[1:][iou < iou_threshold]
    return keep


class PipelineDefinitivo:
    """
    Pipeline principal de detección de personas.
    Carga el modelo YOLOv11 en la NPU Ascend, procesa video en batches de 8 frames,
    detecta personas, les asigna un ID de tracking y cuenta entradas a zona.
    """

    def __init__(self, config_path):
        """
        Inicializa el pipeline con la configuración de zonas.

        Args:
            config_path: ruta al archivo zones.json con coordenadas de zona y línea
        """
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.device_id = 0
        self.input_size = 640
        self.batch_size = 8
        self.conf_threshold = 0.4
        self.iou_threshold = 0.5
        
        zone = self.config.get('zona_rectangular', {})
        self.zone = (zone.get('x1', 400), zone.get('y1', 500),
                     zone.get('x2', 800), zone.get('y2', 700))
        self.line_y = self.config.get('linea_horizontal', {}).get('y', 450)
        
        self.track_counter = 0
        self.track_ids = {}
        self.prev_positions = {}
        self.zone_entries = set()
        self.zone_count = 0
        
    def load_model(self, model_path):
        """
        Carga el modelo .om en la NPU Ascend e inicializa el dispositivo.

        Args:
            model_path: ruta al archivo .om (modelo convertido para Ascend)
        """
        base.mx_init()
        self.model = Model(modelPath=model_path, deviceId=self.device_id)
        print(f"✅ Modelo cargado")
        return True
    
    def preprocess_batch(self, frames):
        """
        Preprocesa un lote de frames para la inferencia:
        - Redimensiona cada frame a 640x640
        - Convierte de BGR (OpenCV) a RGB (modelo)
        - Apila todo en un array numpy de shape (batch, 640, 640, 3)

        Args:
            frames: lista de imágenes BGR (numpy arrays)

        Returns:
            Array numpy uint8 de shape (batch_size, 640, 640, 3) en RGB
        """
        batch_data = []
        for frame in frames:
            resized = cv2.resize(frame, (self.input_size, self.input_size))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            batch_data.append(rgb)
        return np.stack(batch_data, axis=0).astype(np.uint8)
    
    def infer_batch(self, frames):
        """
        Ejecuta la inferencia completa en un batch de frames:
        1. Preprocesa los frames
        2. Transfiere datos a la NPU
        3. Ejecuta inferencia en la NPU
        4. Transfiere resultados de vuelta a CPU
        5. Decodifica las detecciones de cada frame

        Args:
            frames: lista de frames BGR (hasta batch_size frames)

        Returns:
            Lista de listas de detecciones, una por cada frame
        """
        if len(frames) == 0:
            return []
        
        batch_data = self.preprocess_batch(frames)
        input_tensor = Tensor(batch_data)
        input_tensor.to_device(self.device_id)
        outputs = self.model.infer([input_tensor])
        output_tensor = outputs[0]
        output_tensor.to_host()
        data = np.array(output_tensor)
        
        del input_tensor
        
        all_detections = []
        for i in range(len(frames)):
            frame_data = data[i]
            scores = frame_data.T
            detections = self.parse_output(scores, frames[i].shape)
            all_detections.append(detections)
        
        return all_detections
    
    def parse_output(self, scores, frame_shape):
        """
        Decodifica la salida cruda de la NPU en detecciones utilizables.
        Convierte coordenadas normalizadas (640x640) a las dimensiones originales,
        filtra por confianza y tamaño mínimo, aplica NMS y asigna IDs de tracking.

        Args:
            scores: tensor de salida transpuesto (cada fila = [cx, cy, w, h, conf, ...])
            frame_shape: shape del frame original para escalar coordenadas

        Returns:
            Lista de dicts con 'bbox', 'confidence' y 'track_id'
        """
        raw_detections = []
        for score in scores:
            obj_conf = score[4]
            if obj_conf > self.conf_threshold:
                cx = score[0]
                cy = score[1]
                w = score[2]
                h = score[3]
                
                orig_h, orig_w = frame_shape[:2]
                scale_x = orig_w / 640
                scale_y = orig_h / 640
                
                x1 = int((cx - w/2) * scale_x)
                y1 = int((cy - h/2) * scale_y)
                x2 = int((cx + w/2) * scale_x)
                y2 = int((cy + h/2) * scale_y)
                
                x = max(0, min(x1, x2))
                y = max(0, min(y1, y2))
                w_int = abs(x2 - x1)
                h_int = abs(y2 - y1)
                
                # Filtro de tamaño mínimo para evitar falsos positivos
                if w_int > 30 and h_int > 80:
                    raw_detections.append({'bbox': [x, y, w_int, h_int], 'confidence': obj_conf})
        
        if raw_detections:
            boxes = [d['bbox'] for d in raw_detections]
            scores = [d['confidence'] for d in raw_detections]
            keep = nms(boxes, scores, self.iou_threshold)
            final = []
            for idx in keep:
                det = raw_detections[idx]
                x, y, w, h = det['bbox']
                track_id = self.get_track_id(x + w//2, y + h)
                final.append({
                    'bbox': det['bbox'],
                    'confidence': det['confidence'],
                    'track_id': track_id
                })
            return final
        return []
    
    def get_track_id(self, x, y):
        """
        Tracking simple por distancia euclidiana.
        Compara la posición actual (pies de la persona) con las posiciones
        conocidas del frame anterior. Si hay una persona cercana (<50px),
        se le asigna el mismo ID. Si no, se crea un nuevo ID.

        Args:
            x: coordenada X del centro inferior de la persona
            y: coordenada Y del pie de la persona

        Returns:
            ID numérico asignado a esta persona
        """
        best_id = None
        best_dist = 100
        for tid, (lx, ly) in self.track_ids.items():
            dist = ((x - lx)**2 + (y - ly)**2)**0.5
            if dist < best_dist:
                best_dist = dist
                best_id = tid
        if best_id is None or best_dist > 50:
            self.track_counter += 1
            best_id = self.track_counter
        self.track_ids[best_id] = (x, y)
        return best_id
    
    def process_detections(self, detections):
        """
        Analiza las detecciones para contar entradas a zona y cruces de línea.
        - Si los pies de una persona están dentro de la zona → se cuenta como entrada
        - Si los pies cruzan la línea horizontal de arriba a abajo → se registra cruce

        Args:
            detections: lista de detecciones con 'bbox' y 'track_id'
        """
        for det in detections:
            x, y, w, h = det['bbox']
            cx = x + w // 2
            by = y + h
            tid = det['track_id']
            if (self.zone[0] <= cx <= self.zone[2] and self.zone[1] <= by <= self.zone[3]):
                if tid not in self.zone_entries:
                    self.zone_entries.add(tid)
                    self.zone_count += 1
                    print(f"   🔴 ZONE_ENTRY: ID={tid}, Total={self.zone_count}")
            if tid in self.prev_positions:
                prev_y = self.prev_positions[tid]
                if prev_y < self.line_y <= by:
                    print(f"   📏 LINE_CROSS: ID={tid}, Y={by}")
            self.prev_positions[tid] = by
    
    def draw_frame(self, frame, detections):
        """
        Dibuja las anotaciones visuales sobre el frame:
        - Rectángulo verde semitransparente (zona de conteo)
        - Línea roja horizontal (línea de cruce)
        - Bounding boxes de colores con ID y confianza por persona
        - Contador de personas en la zona

        Args:
            frame: imagen BGR original
            detections: lista de detecciones con 'bbox', 'confidence', 'track_id'

        Returns:
            Frame anotado (copia del original con dibujos superpuestos)
        """
        overlay = frame.copy()
        cv2.rectangle(overlay, (self.zone[0], self.zone[1]), 
                     (self.zone[2], self.zone[3]), (0, 255, 0), -1)
        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
        cv2.line(frame, (0, self.line_y), (frame.shape[1], self.line_y), (0, 0, 255), 3)
        cv2.putText(frame, f"Personas: {self.zone_count}", 
                   (self.zone[0] + 10, self.zone[1] + 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        for det in detections:
            x, y, w, h = det['bbox']
            conf = det['confidence']
            tid = det['track_id']
            color = (hash(str(tid)) % 256, (hash(str(tid)) // 256) % 256, 255)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, f"ID:{tid} {conf:.2f}", (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame
    
    def run(self, video_path, model_path):
        """
        Ejecuta el pipeline completo:
        1. Carga el modelo en la NPU
        2. Lee todos los frames del video
        3. Procesa en batches de 8
        4. Detecta, trackea y cuenta personas
        5. Genera video de salida con anotaciones

        Args:
            video_path: ruta al video de entrada (.mp4)
            model_path: ruta al modelo .om para Ascend
        """
        print("=" * 60)
        print("🎥 PIPELINE DEFINITIVO - BATCH 8")
        print("=" * 60)
        
        self.load_model(model_path)
        
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)
        output_video = os.path.join(output_dir, 'output_definitivo.mp4')
        out = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
        
        print(f"\n📹 Video: {width}x{height}, {total_frames} frames")
        print("🚀 Procesando...\n")
        
        # Cargar todos los frames en memoria
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
        
        frame_count = 0
        times = []
        
        # Procesar en batches de 8 frames
        for batch_start in range(0, len(frames), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(frames))
            batch_frames = frames[batch_start:batch_end]
            
            # Rellenar batch incompleto con el último frame (NPU requiere batch fijo)
            original_count = len(batch_frames)
            if original_count < self.batch_size:
                last_frame = batch_frames[-1]
                while len(batch_frames) < self.batch_size:
                    batch_frames.append(last_frame)
            
            start = time.time()
            batch_dets = self.infer_batch(batch_frames)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            
            # Solo procesar los frames reales (no los de relleno)
            for i in range(original_count):
                self.process_detections(batch_dets[i])
                frame_out = self.draw_frame(batch_frames[i], batch_dets[i])
                out.write(frame_out)
                frame_count += 1
            
            if frame_count % 60 == 0:
                avg = sum(times[-30:]) / min(30, len(times))
                fps_batch = (self.batch_size * len(times)) / (sum(times) / 1000) if times else 0
                print(f"   Frame {frame_count}/{total_frames} | {fps_batch:.1f} FPS | Zona: {self.zone_count}")
        
        out.release()
        
        total_time = sum(times) / 1000
        effective_fps = frame_count / total_time if total_time > 0 else 0
        print(f"\n✅ FPS efectivo: {effective_fps:.1f}")
        print(f"   Personas en zona: {self.zone_count}")
        print(f"   Video guardado: {output_video}")


if __name__ == "__main__":
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(SCRIPT_DIR, '../config', 'zones.json')
    video_path = os.path.join(SCRIPT_DIR, '../videos', 'videotest.mp4')
    model_path = os.path.join(SCRIPT_DIR, '../models', 'yolov11_bs8_rgb.om')

    pipeline = PipelineDefinitivo(config_path)
    pipeline.run(video_path, model_path)
