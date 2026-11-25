"""
DocuShield RESTful API Application
==================================
Exposes endpoints for file uploads, job tracking, real-time metrics,
and interactive Chaos Engineering experiments.
"""

import os
import time
import uuid
import hashlib
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.aws_clients import s3_client, sqs_client, dynamo_client, sns_client, local_cloud
from backend.resilience import chaos_control, resilient_retry
from backend.worker import worker_service

app = FastAPI(
    title="DocuShield AWS Resilient Architecture",
    description="Enterprise Resilient Document Processing & Chaos Defense Platform on AWS",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    # Start the distributed worker fleet
    worker_service.start()


@app.on_event("shutdown")
def shutdown_event():
    worker_service.stop()


# =============================================================================
# FRONTEND DASHBOARD
# =============================================================================
FRONTEND_FILE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    if FRONTEND_FILE.exists():
        with open(FRONTEND_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>DocuShield API Running. (frontend/index.html not found)</h1>"


# =============================================================================
# DOCUMENT INGESTION & JOB LIFECYCLE
# =============================================================================
@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    custom_name: Optional[str] = Form(None)
):
    try:
        content = await file.read()
        filename = custom_name or file.filename or "uploaded_doc.txt"
        file_size = len(content)
        file_hash = hashlib.sha256(content).hexdigest()
        
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        raw_s3_key = f"raw/{job_id}_{filename}"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Store in S3 Raw Bucket
        s3_uri = s3_client.upload_bytes(
            bucket=config.S3_RAW_BUCKET,
            key=raw_s3_key,
            data=content,
            content_type=file.content_type or "application/octet-stream"
        )

        # 2. Register initial state in DynamoDB
        job_record = {
            "job_id": job_id,
            "filename": filename,
            "file_size": file_size,
            "sha256": file_hash,
            "status": "QUEUED",
            "raw_s3_key": raw_s3_key,
            "raw_s3_uri": s3_uri,
            "created_at": now_str,
            "updated_at": now_str,
            "is_poison_pill": False
        }
        dynamo_client.put_job(job_record)

        # 3. Queue task in Amazon SQS
        sqs_message_id = sqs_client.send_task({
            "job_id": job_id,
            "filename": filename,
            "raw_s3_key": raw_s3_key,
            "sha256": file_hash,
            "is_poison_pill": False
        })

        return {
            "status": "QUEUED",
            "job_id": job_id,
            "s3_uri": s3_uri,
            "sqs_message_id": sqs_message_id,
            "message": "File successfully received, persisted in S3, and queued in SQS."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
def get_jobs():
    return dynamo_client.list_jobs(limit=100)


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str):
    job = dynamo_client.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/metrics")
def get_system_metrics():
    queue_stats = sqs_client.get_queue_stats()
    all_jobs = dynamo_client.list_jobs(limit=200)

    total_jobs = len(all_jobs)
    completed = sum(1 for j in all_jobs if j.get("status") == "COMPLETED")
    failed = sum(1 for j in all_jobs if j.get("status") in ("FAILED", "DLQ_QUARANTINE"))
    processing = sum(1 for j in all_jobs if j.get("status") in ("PROCESSING", "RETRYING_IN_SQS"))
    queued = sum(1 for j in all_jobs if j.get("status") == "QUEUED")

    account_id = os.getenv("AWS_ACCOUNT_ID", "211409309904")
    return {
        "mode": f"AWS Cloud (Acc: {account_id})" if not config.SIMULATE_AWS else "Local Resilient Simulator",
        "app_env": config.APP_ENV,
        "region": config.AWS_REGION,
        "queue": queue_stats,
        "jobs": {
            "total": total_jobs,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "queued": queued
        },
        "worker": {
            "is_running": worker_service.is_running,
            "processed_count": worker_service.processed_count,
            "failure_count": worker_service.failure_count
        },
        "chaos_status": {
            "crash_worker_next": chaos_control.crash_worker_next,
            "throttle_database": chaos_control.throttle_database,
            "fail_s3_upload": chaos_control.fail_s3_upload,
            "recent_incidents": chaos_control.simulated_incidents[-10:]
        }
    }


# =============================================================================
# CHAOS ENGINEERING & RESILIENCE TESTING ENDPOINTS
# =============================================================================
@app.post("/api/chaos/crash-worker")
def trigger_worker_crash():
    chaos_control.crash_worker_next = True
    return {
        "status": "ARMED",
        "action": "Next worker execution will crash abruptly to test SQS Visibility Timeout recovery without message loss."
    }


@app.post("/api/chaos/inject-poison-pill")
def inject_poison_pill():
    """Injects an unprocessable task to test SQS Redrive Policy & DLQ isolation."""
    job_id = f"poison-{uuid.uuid4().hex[:8]}"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # Put in DynamoDB
    job_record = {
        "job_id": job_id,
        "filename": "MALFORMED_CORRUPT_PAYLOAD.bin",
        "file_size": 1337,
        "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "status": "QUEUED",
        "raw_s3_key": "raw/corrupt_file.bin",
        "created_at": now_str,
        "updated_at": now_str,
        "is_poison_pill": True
    }
    dynamo_client.put_job(job_record)

    # Queue in SQS with poison flag
    msg_id = sqs_client.send_task({
        "job_id": job_id,
        "filename": "MALFORMED_CORRUPT_PAYLOAD.bin",
        "raw_s3_key": "raw/corrupt_file.bin",
        "is_poison_pill": True
    })

    chaos_control.log_incident("POISON_PILL_INJECTED", f"Job {job_id} injected into SQS task queue.")
    return {
        "status": "INJECTED",
        "job_id": job_id,
        "message_id": msg_id,
        "expected_behavior": "Worker will fail 3 times -> SQS redrives message to Dead Letter Queue -> SNS Alert triggered."
    }


@app.post("/api/chaos/throttle-db")
def trigger_db_throttling():
    chaos_control.throttle_database = True
    return {
        "status": "ARMED",
        "action": "DynamoDB will simulate ProvisionedThroughputExceededException on next write, proving Exponential Backoff & Jitter recovery."
    }


@app.post("/api/chaos/fail-s3")
def trigger_s3_failure():
    chaos_control.fail_s3_upload = True
    return {
        "status": "ARMED",
        "action": "S3 will simulate 503 Service Unavailable on next upload to verify retry resilience."
    }


@app.post("/api/dlq/replay")
def replay_dlq():
    count = sqs_client.replay_dlq_messages()
    return {
        "status": "SUCCESS",
        "replayed_messages": count,
        "message": f"Successfully replayed {count} quarantined messages from DLQ back to task queue."
    }


@app.post("/api/reset")
def reset_system():
    chaos_control.reset_all()
    if config.SIMULATE_AWS:
        with local_cloud.lock:
            local_cloud.task_queue.clear()
            local_cloud.dlq_queue.clear()
            local_cloud.database.clear()
            local_cloud.published_alerts.clear()
            local_cloud._save_db()
    return {"status": "RESET_COMPLETE"}
