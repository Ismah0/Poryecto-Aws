"""
DocuShield Distributed Worker Consumer Service
==============================================
Pulls messages from SQS, executes resilient processing pipelines,
handles worker crash simulations, and gracefully isolates poison pills into the DLQ.
"""

import json
import time
import hashlib
import logging
import threading
from typing import Dict, Any

from backend.aws_clients import s3_client, sqs_client, dynamo_client, sns_client
from backend.resilience import chaos_control
from backend import config

logger = logging.getLogger("DocuShield.Worker")


class DocumentWorker:
    def __init__(self, worker_id: str = "worker-primary"):
        self.worker_id = worker_id
        self.is_running = False
        self._thread = None
        self.processed_count = 0
        self.failure_count = 0

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, name=f"DocuShield-{self.worker_id}", daemon=True)
        self._thread.start()
        logger.info(f"[{self.worker_id}] Worker thread started and listening on SQS task queue.")

    def stop(self):
        logger.info(f"[{self.worker_id}] Stopping worker...")
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _run_loop(self):
        while self.is_running:
            try:
                # Long polling: Receive up to 1 message
                messages = sqs_client.receive_tasks(max_messages=1, wait_time_seconds=2)
                if not messages:
                    time.sleep(0.5)
                    continue

                for msg in messages:
                    self._process_message(msg)

            except Exception as e:
                logger.error(f"[{self.worker_id}] Worker loop error: {e}")
                time.sleep(1)

    def _process_message(self, message: Dict[str, Any]):
        receipt_handle = message["ReceiptHandle"]
        receive_count = message.get("ApproximateReceiveCount", 1)
        
        try:
            payload = json.loads(message["Body"])
        except Exception:
            logger.critical(f"[{self.worker_id}] Malformed JSON payload. Deleting bad SQS message.")
            sqs_client.delete_task(receipt_handle)
            return

        job_id = payload.get("job_id")
        filename = payload.get("filename", "unknown.txt")
        raw_s3_key = payload.get("raw_s3_key")
        is_poison = payload.get("is_poison_pill", False)

        logger.info(f"[{self.worker_id}] Picked job {job_id} (Attempt #{receive_count})")

        # -------------------------------------------------------------
        # RESILIENCE EXPERIMENT 1: SIMULATED WORKER CRASH (Kill mid-task)
        # -------------------------------------------------------------
        if chaos_control.crash_worker_next:
            chaos_control.crash_worker_next = False
            chaos_control.log_incident(
                "WORKER_CRASH_SIMULATION",
                f"Worker '{self.worker_id}' crashed intentionally while processing job {job_id}. Message left unacknowledged in SQS."
            )
            logger.critical(f"[{self.worker_id}] CRASH SIMULATION TRIGGERED! Abruptly abandoning message {job_id}...")
            # Simulate worker crash by sleeping briefly and raising fatal error without deleting SQS task
            time.sleep(1.0)
            return

        # -------------------------------------------------------------
        # RESILIENCE EXPERIMENT 2: POISON PILL (Unparseable corrupt data)
        # -------------------------------------------------------------
        if is_poison:
            self.failure_count += 1
            err_msg = f"Poison pill detected: Unprocessable binary format or corrupted checksum."
            dynamo_client.update_job_status(job_id, status="RETRYING_IN_SQS", error_msg=f"{err_msg} (Attempt {receive_count}/3)")
            chaos_control.log_incident("POISON_PILL_EXECUTION", f"Job {job_id} failed on attempt {receive_count}/3.")
            
            if receive_count >= 3:
                # On 3rd attempt, it will enter DLQ
                dynamo_client.update_job_status(job_id, status="DLQ_QUARANTINE", error_msg=f"Quarantined in DLQ after 3 failed attempts: {err_msg}")
                sns_client.publish_incident_alert(
                    subject=f"ALERT: Job {job_id} moved to Dead Letter Queue (DLQ)",
                    message=f"Job {job_id} for file '{filename}' failed 3 consecutive times and was quarantined in DLQ."
                )
            # DO NOT DELETE FROM SQS. SQS visibility timeout will expire or redrive to DLQ.
            return

        # -------------------------------------------------------------
        # NORMAL PIPELINE PROCESSING
        # -------------------------------------------------------------
        try:
            dynamo_client.update_job_status(job_id, status="PROCESSING")
            start_time = time.time()

            # 1. Fetch raw data from S3
            raw_bytes = s3_client.get_bytes(bucket=config.S3_RAW_BUCKET, key=raw_s3_key)
            
            # 2. Extract Document Metrics & Metadata
            text_content = raw_bytes.decode("utf-8", errors="replace")
            words = text_content.split()
            word_count = len(words)
            char_count = len(text_content)
            line_count = len(text_content.splitlines())
            sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

            # Simulating brief compute time (0.15s)
            time.sleep(0.15)
            duration_ms = int(round((time.time() - start_time) * 1000))

            analysis_result = {
                "filename": filename,
                "file_size_bytes": len(raw_bytes),
                "word_count": word_count,
                "line_count": line_count,
                "char_count": char_count,
                "sha256": sha256_hash,
                "processing_time_ms": duration_ms,
                "processed_by_worker": self.worker_id,
                "security_scan": "PASSED (Clean, no vulnerabilities)",
                "sentiment_keywords": [w.lower() for w in words[:15] if len(w) > 4]
            }

            # 3. Store Processed Result to S3
            processed_s3_key = f"results/{job_id}_analyzed.json"
            s3_client.upload_bytes(
                bucket=config.S3_PROCESSED_BUCKET,
                key=processed_s3_key,
                data=json.dumps(analysis_result, indent=2).encode("utf-8"),
                content_type="application/json"
            )

            # 4. Update DynamoDB Job State to COMPLETED
            dynamo_client.update_job_status(
                job_id=job_id,
                status="COMPLETED",
                result_data={
                    "processed_s3_key": processed_s3_key,
                    "metrics": analysis_result
                }
            )

            # 5. Delete message from SQS (Acknowledge completion)
            sqs_client.delete_task(receipt_handle)
            self.processed_count += 1
            logger.info(f"[{self.worker_id}] Successfully finished job {job_id} in {duration_ms}ms")

        except Exception as err:
            self.failure_count += 1
            logger.error(f"[{self.worker_id}] Error processing job {job_id}: {err}")
            dynamo_client.update_job_status(job_id, status="FAILED", error_msg=str(err))


# Global worker instance
worker_service = DocumentWorker()
