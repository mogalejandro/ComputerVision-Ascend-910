#!/usr/bin/env python3
"""
Manejador de flujos RTSP para el pipeline de vigilancia.
"""

import cv2
import time
import logging
import threading
from typing import Optional
from pipeline import PipelineDefinitivo  # Tu pipeline original

logger = logging.getLogger(__name__)

class RTSPHandler:
    """
    Clase que maneja la conexión RTSP, procesamiento y publicación.
    """
    
    def __init__(self, pipeline: PipelineDefinitivo):
        """
        Inicializa el manejador RTSP.
        
        Args:
            pipeline: Instancia de PipelineDefinitivo con el modelo cargado
        """
        self.pipeline = pipeline
        self.is_running = False
        self.thread = None
        self.stats = {
            'frames_processed': 0,
            'fps': 0,
            'start_time': None,
            'end_time': None
        }
        
    def init_rtsp_output(self, width: int, height: int, fps: int) -> bool:
        """
        Inicializa el pipeline de GStreamer para publicar en RTSP.
        """
        try:
            # Pipeline GStreamer optimizado para baja latencia
            pipeline_str = (
                f'appsrc name=source ! videoconvert ! '
                f'video/x-raw,format=BGR ! '
                f'x264enc speed-preset=ultrafast tune=zerolatency bitrate=2000 ! '
                f'h264parse ! '
                f'rtph264pay name=pay0 pt=96 ! '
                f'udpsink host=127.0.0.1 port=8554'
            )
            
            # Si tienes mediamtx corriendo, puedes usar este pipeline alternativo:
            # pipeline_str = (
            #     f'appsrc name=source ! videoconvert ! '
            #     f'x264enc speed-preset=ultrafast tune=zerolatency bitrate=2000 ! '
            #     f'h264parse ! '
            #     f'rtmp2sink location=rtmp://localhost/live/stream_{id(self)}'
            # )
            
            self.pipeline.out = cv2.VideoWriter(
                pipeline_str,
                cv2.CAP_GSTREAMER,
                0,
                fps,
                (width, height)
            )
            
            if not self.pipeline.out.isOpened():
                logger.error("❌ No se pudo abrir el pipeline RTSP de salida")
                return False
                
            logger.info(f"✅ Salida RTSP inicializada en puerto 8554")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error al inicializar salida RTSP: {e}")
            return False
    
    def process_rtsp_stream(self, rtsp_url: str, output_url: Optional[str] = None):
        """
        Procesa un flujo RTSP y publica el resultado.
        
        Args:
            rtsp_url: URL del flujo RTSP de entrada
            output_url: URL opcional para publicación (si no se usa GStreamer)
        """
        self.is_running = True
        self.stats['start_time'] = time.time()
        
        logger.info(f"🎥 Conectando a RTSP: {rtsp_url}")
        
        # Abrir stream RTSP
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            raise Exception(f"No se pudo abrir el RTSP: {rtsp_url}")
        
        # Obtener propiedades del stream
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        logger.info(f"📹 Stream: {width}x{height} @ {fps} FPS")
        
        # Inicializar salida RTSP
        if not self.init_rtsp_output(width, height, fps):
            cap.release()
            raise Exception("No se pudo inicializar la salida RTSP")
        
        frame_buffer = []
        frame_count = 0
        last_log_time = time.time()
        
        try:
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("⚠️ Fin del stream RTSP o error de lectura")
                    break
                
                frame_buffer.append(frame)
                
                # Procesar cuando tengamos batch_size frames
                if len(frame_buffer) >= self.pipeline.batch_size:
                    batch_frames = frame_buffer[:self.pipeline.batch_size]
                    frame_buffer = frame_buffer[self.pipeline.batch_size:]
                    
                    # Inferencia en batch
                    batch_dets = self.pipeline.infer_batch(batch_frames)
                    
                    # Procesar cada frame
                    for i, det in enumerate(batch_dets):
                        self.pipeline.process_detections(det)
                        frame_out = self.pipeline.draw_frame(batch_frames[i], det)
                        self.pipeline.out.write(frame_out)
                        frame_count += 1
                    
                    # Actualizar estadísticas
                    self.stats['frames_processed'] = frame_count
                    
                    # Logging periódico
                    current_time = time.time()
                    if current_time - last_log_time >= 5.0:  # Cada 5 segundos
                        elapsed = current_time - self.stats['start_time']
                        real_fps = frame_count / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"📊 Frame {frame_count} | "
                            f"{real_fps:.1f} FPS | "
                            f"Zona: {self.pipeline.zone_count}"
                        )
                        last_log_time = current_time
                
                # Pequeña pausa para evitar saturar la CPU
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            logger.info("⏹️ Procesamiento interrumpido por el usuario")
        except Exception as e:
            logger.error(f"❌ Error en procesamiento RTSP: {e}")
            raise
        finally:
            # Liberar recursos
            cap.release()
            if self.pipeline.out:
                self.pipeline.out.release()
            
            self.is_running = False
            self.stats['end_time'] = time.time()
            
            total_time = self.stats['end_time'] - self.stats['start_time']
            avg_fps = frame_count / total_time if total_time > 0 else 0
            logger.info(f"✅ Procesamiento completado")
            logger.info(f"   Frames: {frame_count} | FPS: {avg_fps:.1f}")
            logger.info(f"   Personas en zona: {self.pipeline.zone_count}")
    
    def start(self, rtsp_url: str):
        """
        Inicia el procesamiento en un hilo separado.
        
        Args:
            rtsp_url: URL del flujo RTSP a procesar
            
        Returns:
            threading.Thread: El hilo de procesamiento
        """
        if self.thread and self.thread.is_alive():
            logger.warning("⚠️ Ya hay un procesamiento en curso")
            return self.thread
        
        self.thread = threading.Thread(
            target=self.process_rtsp_stream,
            args=(rtsp_url,),
            daemon=True
        )
        self.thread.start()
        return self.thread
    
    def stop(self):
        """Detiene el procesamiento."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            logger.info("⏹️ Procesamiento detenido")
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del procesamiento."""
        return self.stats
