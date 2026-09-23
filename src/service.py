#!/usr/bin/env python3
"""
Servicio de Inferencia Asíncrona para ModelArts
Puerto 8080 - Procesamiento de flujos RTSP con YOLO
"""

import os
import json
import uuid
import threading
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify

# Importar tus módulos
from pipeline import PipelineDefinitivo
from rtsp_handler import RTSPHandler

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Directorios base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'yolov11_bs8_rgb.om')
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'zones.json')

# Estado global
tasks = {}
pipeline_instance = None

# ==================== INICIALIZACIÓN ====================

def init_pipeline():
    """Inicializa el pipeline una sola vez al inicio."""
    global pipeline_instance
    try:
        logger.info("🚀 Inicializando pipeline...")
        pipeline_instance = PipelineDefinitivo(CONFIG_PATH)
        pipeline_instance.load_model(MODEL_PATH)
        logger.info("✅ Pipeline inicializado correctamente")
        return True
    except Exception as e:
        logger.error(f"❌ Error al inicializar pipeline: {e}")
        return False

# Inicializar pipeline al iniciar el servicio
if not init_pipeline():
    logger.error("No se pudo inicializar el pipeline. El servicio no funcionará correctamente.")

# ==================== ENDPOINTS ====================

@app.route('/', methods=['POST'])
def start_inference():
    """
    Inicia una tarea de inferencia para un flujo RTSP.
    """
    try:
        # 1. Validar solicitud
        data = request.get_json()
        if not data or 'rtsp_url' not in data:
            return jsonify({
                "error": "Se requiere 'rtsp_url' en el body"
            }), 400
        
        rtsp_url = data['rtsp_url']
        
        # Validar URL RTSP
        if not rtsp_url.startswith('rtsp://'):
            return jsonify({
                "error": "URL inválida. Debe comenzar con 'rtsp://'"
            }), 400
        
        # 2. Generar ID de tarea
        task_id = str(uuid.uuid4())
        
        # 3. Crear tarea
        task = {
            'id': task_id,
            'rtsp_url': rtsp_url,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'result': None,
            'error': None,
            'stats': None
        }
        tasks[task_id] = task
        
        # 4. Iniciar procesamiento en hilo separado
        def process_task():
            try:
                task['status'] = 'processing'
                task['started_at'] = datetime.now().isoformat()
                logger.info(f"🎬 [Task {task_id}] Iniciando procesamiento de {rtsp_url}")
                
                # Crear instancia del manejador RTSP
                # Nota: Usamos una copia del pipeline para evitar conflictos
                handler = RTSPHandler(pipeline_instance)
                handler.process_rtsp_stream(rtsp_url)
                
                # Actualizar resultado
                task['status'] = 'completed'
                task['completed_at'] = datetime.now().isoformat()
                task['result'] = {
                    'person_count': pipeline_instance.zone_count,
                    'rtsp_output': f"rtsp://localhost:8554/live_{task_id}"
                }
                task['stats'] = handler.get_stats()
                
                logger.info(f"✅ [Task {task_id}] Completada. Personas: {pipeline_instance.zone_count}")
                
            except Exception as e:
                task['status'] = 'failed'
                task['error'] = str(e)
                task['completed_at'] = datetime.now().isoformat()
                logger.error(f"❌ [Task {task_id}] Error: {e}")
        
        thread = threading.Thread(target=process_task, daemon=True)
        thread.start()
        
        # 5. Responder inmediatamente
        return jsonify({
            "task_id": task_id,
            "status": "pending",
            "message": "Tarea creada exitosamente",
            "rtsp_url": rtsp_url
        }), 202
        
    except Exception as e:
        logger.error(f"❌ Error en /: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    Consulta el estado de una tarea.
    """
    try:
        if task_id not in tasks:
            return jsonify({"error": f"Tarea {task_id} no encontrada"}), 404
        
        task = tasks[task_id]
        
        response = {
            "task_id": task['id'],
            "status": task['status'],
            "created_at": task['created_at'],
            "started_at": task['started_at'],
            "completed_at": task['completed_at']
        }
        
        if task['status'] == 'completed':
            response['result'] = task['result']
            response['stats'] = task['stats']
        elif task['status'] == 'failed':
            response['error'] = task['error']
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Error en /status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check para ModelArts.
    """
    active_tasks = len([t for t in tasks.values() if t['status'] == 'processing'])
    
    return jsonify({
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "active_tasks": active_tasks,
        "total_tasks": len(tasks)
    }), 200

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Métricas del servicio.
    """
    total = len(tasks)
    pending = len([t for t in tasks.values() if t['status'] == 'pending'])
    processing = len([t for t in tasks.values() if t['status'] == 'processing'])
    completed = len([t for t in tasks.values() if t['status'] == 'completed'])
    failed = len([t for t in tasks.values() if t['status'] == 'failed'])
    
    return jsonify({
        "total_tasks": total,
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "uptime_seconds": int(time.time() - app.start_time)
    }), 200

@app.route('/', methods=['GET'])
def index():
    """
    Endpoint raíz para verificar que el servicio está vivo.
    """
    return jsonify({
        "service": "ModelArts Inference Service",
        "version": "1.0",
        "endpoints": {
            "POST /": "Iniciar inferencia",
            "GET /status/<task_id>": "Consultar estado",
            "GET /health": "Health check",
            "GET /metrics": "Métricas"
        }
    }), 200

# ==================== INICIO DEL SERVIDOR ====================

if __name__ == "__main__":
    app.start_time = time.time()
    logger.info("=" * 60)
    logger.info("🚀 Servidor de Inferencia ModelArts")
    logger.info("=" * 60)
    logger.info("📋 Endpoints:")
    logger.info("   POST / - Iniciar inferencia")
    logger.info("   GET /status/<task_id> - Consultar estado")
    logger.info("   GET /health - Health check")
    logger.info("   GET /metrics - Métricas")
    logger.info("=" * 60)
    
    # ¡IMPORTANTE: host="0.0.0.0", port=8080 es OBLIGATORIO!
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
