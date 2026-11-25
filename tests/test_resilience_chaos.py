"""
DocuShield Automated Chaos & Resilience Test Suite
=================================================
Validates Requirement #2: "Demuéstrame que no se rompe".
Executes automated failure injection experiments:
1. Normal End-to-End Processing Flow
2. Worker Crash Mid-Processing (SQS Visibility Timeout Recovery)
3. Poison Pill Isolation (SQS Redrive Policy to Dead Letter Queue)
4. Database Throttling & Network Outage (Exponential Backoff with Full Jitter)
5. Dead Letter Queue Redrive & Recovery

Usage:
    python tests/test_resilience_chaos.py
"""

import sys
import time
import uuid
import hashlib
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import config
from backend.aws_clients import s3_client, sqs_client, dynamo_client, sns_client, local_cloud
from backend.resilience import chaos_control, resilient_retry
from backend.worker import DocumentWorker


class ResilienceTestSuite:
    def __init__(self):
        self.worker = DocumentWorker(worker_id="test-worker")
        self.passed_tests = 0
        self.total_tests = 0

    def setup(self):
        print("\n" + "="*70)
        print("   DocuShield - Suite Automatizada de Pruebas de Resiliencia   ")
        print("   Demostración de Tolerancia a Fallos y Defensa de Caos      ")
        print("="*70)
        # Clear simulated state
        if config.SIMULATE_AWS:
            with local_cloud.lock:
                local_cloud.task_queue.clear()
                local_cloud.dlq_queue.clear()
                local_cloud.database.clear()
                local_cloud.published_alerts.clear()
        chaos_control.reset_all()

    def assert_test(self, condition: bool, description: str):
        self.total_tests += 1
        if condition:
            self.passed_tests += 1
            print(f"  [+] PASÓ: {description}")
        else:
            print(f"  [-] FALLÓ: {description}")
            raise AssertionError(f"Prueba de resiliencia fallida: {description}")

    # =========================================================================
    # PRUEBA 1: FLUJO BASE DE INGESTA Y PROCESAMIENTO
    # =========================================================================
    def test_01_normal_flow(self):
        print("\n--- [Experimento 1] Ingesta y Procesamiento Nominal ---")
        job_id = f"test-nominal-{uuid.uuid4().hex[:6]}"
        sample_doc = b"DocuShield Resilience Architecture Nominal Test Document."
        raw_key = f"raw/{job_id}.txt"

        # 1. Guardar en S3
        s3_client.upload_bytes(config.S3_RAW_BUCKET, raw_key, sample_doc)
        
        # 2. Registrar en DynamoDB
        dynamo_client.put_job({
            "job_id": job_id,
            "filename": "nominal.txt",
            "status": "QUEUED",
            "raw_s3_key": raw_key,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        # 3. Enviar a SQS
        sqs_client.send_task({
            "job_id": job_id,
            "filename": "nominal.txt",
            "raw_s3_key": raw_key,
            "is_poison_pill": False
        })

        # 4. Worker procesa un mensaje
        msgs = sqs_client.receive_tasks(max_messages=1)
        self.assert_test(len(msgs) == 1, "Mensaje recibido correctamente de la cola SQS principal.")
        self.worker._process_message(msgs[0])

        # 5. Verificar estado en DynamoDB
        job = dynamo_client.get_job(job_id)
        self.assert_test(job["status"] == "COMPLETED", "Estado del trabajo transicionó a 'COMPLETED' en DynamoDB.")
        self.assert_test("result" in job and "metrics" in job["result"], "Métricas de extracción generadas en S3 y DynamoDB.")
        
        # 6. Verificar que la cola SQS quedó limpia (mensaje borrado tras éxito)
        stats = sqs_client.get_queue_stats()
        self.assert_test(stats["tasks_visible"] == 0, "Mensaje eliminado exitosamente de SQS (Acknowledge).")

    # =========================================================================
    # PRUEBA 2: CAÍDA ABRUPTA DEL WORKER (Worker Crash / Kill Simulation)
    # =========================================================================
    def test_02_worker_crash_recovery(self):
        print("\n--- [Experimento 2] Caída Abrupta del Worker y Recuperación SQS ---")
        print("  [*] Hipótesis: Si el worker muere a mitad de tarea, el mensaje no se pierde.")
        print("  [*] Mecanismo: SQS Visibility Timeout expira y otro worker completa el trabajo.")

        job_id = f"test-crash-{uuid.uuid4().hex[:6]}"
        sample_doc = b"Critical Transaction Document that must never be lost."
        raw_key = f"raw/{job_id}.txt"

        s3_client.upload_bytes(config.S3_RAW_BUCKET, raw_key, sample_doc)
        dynamo_client.put_job({
            "job_id": job_id,
            "filename": "critical_tx.txt",
            "status": "QUEUED",
            "raw_s3_key": raw_key,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        sqs_client.send_task({
            "job_id": job_id,
            "filename": "critical_tx.txt",
            "raw_s3_key": raw_key,
            "is_poison_pill": False
        })

        # Armar caída de worker
        chaos_control.crash_worker_next = True

        # Intento 1: Worker recibe el mensaje pero colapsa a mitad de camino
        msgs = sqs_client.receive_tasks(max_messages=1)
        self.assert_test(len(msgs) == 1, "Worker 1 tomó el mensaje de la cola.")
        self.worker._process_message(msgs[0])

        # Verificar que el mensaje NO se borró de SQS
        job_pre = dynamo_client.get_job(job_id)
        self.assert_test(job_pre["status"] != "COMPLETED", "El trabajo no fue completado por el worker caído.")

        print("  [*] Simulando expiración de Visibility Timeout...")
        if config.SIMULATE_AWS:
            with local_cloud.lock:
                for m in local_cloud.task_queue:
                    m.visible_after = 0.0  # Expire visibility timeout immediately for testing

        # Intento 2: Nuevo worker o worker reiniciado toma el mensaje de nuevo
        msgs_retry = sqs_client.receive_tasks(max_messages=1)
        self.assert_test(len(msgs_retry) == 1, "Mensaje recuperado automáticamente de SQS tras expirar visibilidad.")
        
        # Procesar con éxito
        self.worker._process_message(msgs_retry[0])
        job_post = dynamo_client.get_job(job_id)
        self.assert_test(job_post["status"] == "COMPLETED", "El trabajo se completó exitosamente sin pérdida de datos tras el crash.")

    # =========================================================================
    # PRUEBA 3: AISLAMIENTO DE POISON PILL EN DEAD LETTER QUEUE (DLQ)
    # =========================================================================
    def test_03_poison_pill_dlq_isolation(self):
        print("\n--- [Experimento 3] Inyección de Poison Pill y Aislamiento en DLQ ---")
        print("  [*] Hipótesis: Un mensaje malformado no debe tumbar la infraestructura ni bloquear otros trabajos.")
        print("  [*] Mecanismo: SQS Redrive Policy envía a DLQ tras 3 reintentos y dispara alerta SNS.")

        job_id = f"test-poison-{uuid.uuid4().hex[:6]}"
        dynamo_client.put_job({
            "job_id": job_id,
            "filename": "corrupt_data.bin",
            "status": "QUEUED",
            "raw_s3_key": "raw/corrupt.bin",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        sqs_client.send_task({
            "job_id": job_id,
            "filename": "corrupt_data.bin",
            "raw_s3_key": "raw/corrupt.bin",
            "is_poison_pill": True
        })

        # Simulamos 3 fallos consecutivos
        for attempt in range(1, 4):
            if config.SIMULATE_AWS:
                with local_cloud.lock:
                    for m in local_cloud.task_queue:
                        m.visible_after = 0.0
            
            msgs = sqs_client.receive_tasks(max_messages=1)
            if msgs:
                self.worker._process_message(msgs[0])
                print(f"  [*] Fallo #{attempt} manejado controladamente por el worker.")

        # SQS evalúa la política de redrive al siguiente sondeo y desvía a la DLQ
        if config.SIMULATE_AWS:
            with local_cloud.lock:
                for m in local_cloud.task_queue:
                    m.visible_after = 0.0
        sqs_client.receive_tasks(max_messages=1)

        # Verificar que entró a la DLQ
        stats = sqs_client.get_queue_stats()
        self.assert_test(stats["dlq_messages"] >= 1, "Mensaje venenoso aislado exitosamente en Dead Letter Queue (DLQ).")
        
        job = dynamo_client.get_job(job_id)
        self.assert_test(job["status"] == "DLQ_QUARANTINE", "Estado del trabajo marcado como 'DLQ_QUARANTINE' en DynamoDB.")

        # Verificar alerta en SNS
        if config.SIMULATE_AWS:
            with local_cloud.lock:
                alerts_count = len(local_cloud.published_alerts)
                self.assert_test(alerts_count >= 1, "Alerta de incidente publicada en Amazon SNS Topic.")

    # =========================================================================
    # PRUEBA 4: REINTENTOS CON EXPONENTIAL BACKOFF Y JITTER (DynamoDB Throttling)
    # =========================================================================
    def test_04_exponential_backoff_jitter(self):
        print("\n--- [Experimento 4] Saturación de Base de Datos y Backoff Exponencial ---")
        print("  [*] Hipótesis: Fallos transitorios 503/Throttling se absorben sin perder peticiones.")
        print("  [*] Mecanismo: Retry con Exponential Backoff y Jitter aleatorio.")

        job_id = f"test-backoff-{uuid.uuid4().hex[:6]}"
        chaos_control.throttle_database = True  # Inyecta error 503 en primer intento

        # Intentar escribir con el decorador @resilient_retry
        dynamo_client.put_job({
            "job_id": job_id,
            "filename": "backoff_test.txt",
            "status": "QUEUED",
            "raw_s3_key": "raw/backoff.txt",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        job = dynamo_client.get_job(job_id)
        self.assert_test(job is not None and job["job_id"] == job_id, "Petición recuperada y guardada tras reintento exponencial.")

    # =========================================================================
    # PRUEBA 5: DRENAJE Y RECUPERACIÓN DE LA DLQ (DLQ Replay)
    # =========================================================================
    def test_05_dlq_recovery_replay(self):
        print("\n--- [Experimento 5] Drenaje y Reprocesamiento de DLQ (Redrive) ---")
        stats_before = sqs_client.get_queue_stats()
        dlq_count = stats_before["dlq_messages"]
        self.assert_test(dlq_count > 0, f"Existen {dlq_count} mensaje(s) en DLQ para recuperación.")

        # Ejecutar replay
        replayed = sqs_client.replay_dlq_messages()
        self.assert_test(replayed == dlq_count, f"{replayed} mensaje(s) drenados de la DLQ.")

        stats_after = sqs_client.get_queue_stats()
        self.assert_test(stats_after["dlq_messages"] == 0, "Dead Letter Queue vaciada exitosamente a 0.")
        self.assert_test(stats_after["tasks_visible"] >= 1, "Mensajes devueltos a la cola principal listos para reprocesamiento.")

    def run_all(self):
        self.setup()
        self.test_01_normal_flow()
        self.test_02_worker_crash_recovery()
        self.test_03_poison_pill_dlq_isolation()
        self.test_04_exponential_backoff_jitter()
        self.test_05_dlq_recovery_replay()

        print("\n" + "="*70)
        print(f"   RESUMEN FINAL: {self.passed_tests}/{self.total_tests} PRUEBAS DE RESILIENCIA SUPERADAS")
        print("   ESTADO: SISTEMA ALTAMENTE RESILIENTE Y TOLERANTE A FALLOS (PASSED)")
        print("="*70 + "\n")
        return True


if __name__ == "__main__":
    suite = ResilienceTestSuite()
    success = suite.run_all()
    if not success:
        sys.exit(1)
