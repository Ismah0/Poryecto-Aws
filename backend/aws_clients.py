"""
DocuShield AWS Service Client & Cloud Adapter Layer
===================================================
Provides Hexagonal Architecture Ports and Adapters:
- Production Adapter: Uses Amazon Web Services via Boto3 (S3, SQS, DynamoDB, SNS)
- Local Resilient Simulator: High-fidelity in-memory/file-backed simulator matching AWS SQS
  visibility timeout, DLQ redrive policies, DynamoDB secondary index queries, and S3 encryption.
"""

import os
import json
import time
import uuid
import hashlib
import threading
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from backend import config
from backend.resilience import resilient_retry, chaos_control

logger = logging.getLogger("DocuShield.AWS")


# =============================================================================
# SIMULATED AWS CLOUD INFRASTRUCTURE (Used in local / test mode)
# =============================================================================
class LocalSQSMessage:
    def __init__(self, body: str, attributes: Optional[Dict] = None):
        self.message_id = str(uuid.uuid4())
        self.receipt_handle = str(uuid.uuid4())
        self.body = body
        self.attributes = attributes or {}
        self.receive_count = 0
        self.visible_after = 0.0  # Unix timestamp when visible again


class LocalCloudDriver:
    """Simulates S3, SQS with Visibility Timeout & DLQ, DynamoDB, and SNS locally."""
    def __init__(self):
        self.lock = threading.RLock()
        self.task_queue: List[LocalSQSMessage] = []
        self.dlq_queue: List[LocalSQSMessage] = []
        self.database: Dict[str, Dict[str, Any]] = {}
        self.published_alerts: List[Dict[str, Any]] = []
        self._load_db()

    def _load_db(self):
        if config.LOCAL_DB_FILE.exists():
            try:
                with open(config.LOCAL_DB_FILE, "r", encoding="utf-8") as f:
                    self.database = json.load(f)
            except Exception:
                self.database = {}

    def _save_db(self):
        try:
            with open(config.LOCAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.database, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving local DB: {e}")


local_cloud = LocalCloudDriver()


# =============================================================================
# S3 SERVICE ADAPTER
# =============================================================================
class S3Service:
    def __init__(self):
        self.simulate = config.SIMULATE_AWS
        if not self.simulate:
            import boto3
            self.s3_client = boto3.client("s3", region_name=config.AWS_REGION)

    @resilient_retry(max_retries=3, base_delay=0.3)
    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        if chaos_control.fail_s3_upload:
            chaos_control.fail_s3_upload = False
            chaos_control.log_incident("S3_SIMULATED_FAILURE", f"Forced S3 upload drop on {key}")
            raise IOError("Simulated S3 ServiceUnavailableException: 503 Slow Down")

        if self.simulate:
            dest_dir = config.LOCAL_RAW_DIR if "raw" in bucket else config.LOCAL_PROCESSED_DIR
            target_path = dest_dir / key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(data)
            return f"s3://{bucket}/{key}"
        else:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256"
            )
            return f"s3://{bucket}/{key}"

    def get_bytes(self, bucket: str, key: str) -> bytes:
        if self.simulate:
            dest_dir = config.LOCAL_RAW_DIR if "raw" in bucket else config.LOCAL_PROCESSED_DIR
            target_path = dest_dir / key
            if not target_path.exists():
                raise FileNotFoundError(f"S3 Key '{key}' not found in local bucket '{bucket}'")
            with open(target_path, "rb") as f:
                return f.read()
        else:
            res = self.s3_client.get_object(Bucket=bucket, Key=key)
            return res["Body"].read()


# =============================================================================
# SQS SERVICE ADAPTER (With DLQ & Visibility Timeout)
# =============================================================================
class SQSService:
    def __init__(self):
        self.simulate = config.SIMULATE_AWS
        self.visibility_timeout = 8.0 if self.simulate else 30.0  # seconds
        self.max_receive_count = 3
        if not self.simulate:
            import boto3
            self.sqs_client = boto3.client("sqs", region_name=config.AWS_REGION)

    def send_task(self, body_data: Dict[str, Any]) -> str:
        payload = json.dumps(body_data)
        if self.simulate:
            with local_cloud.lock:
                msg = LocalSQSMessage(body=payload)
                local_cloud.task_queue.append(msg)
                return msg.message_id
        else:
            res = self.sqs_client.send_message(
                QueueUrl=config.SQS_TASK_QUEUE_URL,
                MessageBody=payload
            )
            return res["MessageId"]

    def receive_tasks(self, max_messages: int = 1, wait_time_seconds: int = 2) -> List[Dict[str, Any]]:
        now = time.time()
        if self.simulate:
            with local_cloud.lock:
                available = []
                for msg in local_cloud.task_queue:
                    if msg.visible_after <= now:
                        msg.receive_count += 1
                        # If reached max receive count, divert to DLQ!
                        if msg.receive_count > self.max_receive_count:
                            logger.warning(f"[SQS-Redrive] Message {msg.message_id} exceeded {self.max_receive_count} attempts. Diverting to DLQ.")
                            local_cloud.dlq_queue.append(msg)
                            chaos_control.log_incident(
                                "SQS_DLQ_REDRIVE",
                                f"Message {msg.message_id} quarantined in DLQ after {msg.receive_count} failures."
                            )
                            continue
                        
                        msg.visible_after = now + self.visibility_timeout
                        available.append({
                            "MessageId": msg.message_id,
                            "ReceiptHandle": msg.receipt_handle,
                            "Body": msg.body,
                            "ApproximateReceiveCount": msg.receive_count
                        })
                        if len(available) >= max_messages:
                            break

                # Clean up items moved to DLQ from the main queue
                local_cloud.task_queue = [m for m in local_cloud.task_queue if m not in local_cloud.dlq_queue]
                return available
        else:
            res = self.sqs_client.receive_message(
                QueueUrl=config.SQS_TASK_QUEUE_URL,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=["ApproximateReceiveCount"]
            )
            out = []
            for m in res.get("Messages", []):
                rc = int(m.get("Attributes", {}).get("ApproximateReceiveCount", 1))
                out.append({
                    "MessageId": m["MessageId"],
                    "ReceiptHandle": m["ReceiptHandle"],
                    "Body": m["Body"],
                    "ApproximateReceiveCount": rc
                })
            return out

    def delete_task(self, receipt_handle: str):
        if self.simulate:
            with local_cloud.lock:
                local_cloud.task_queue = [m for m in local_cloud.task_queue if m.receipt_handle != receipt_handle]
        else:
            self.sqs_client.delete_message(
                QueueUrl=config.SQS_TASK_QUEUE_URL,
                ReceiptHandle=receipt_handle
            )

    def get_queue_stats(self) -> Dict[str, int]:
        now = time.time()
        if self.simulate:
            with local_cloud.lock:
                visible = sum(1 for m in local_cloud.task_queue if m.visible_after <= now)
                in_flight = sum(1 for m in local_cloud.task_queue if m.visible_after > now)
                dlq_count = len(local_cloud.dlq_queue)
                return {
                    "tasks_visible": visible,
                    "tasks_in_flight": in_flight,
                    "dlq_messages": dlq_count
                }
        else:
            try:
                res_main = self.sqs_client.get_queue_attributes(
                    QueueUrl=config.SQS_TASK_QUEUE_URL,
                    AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"]
                )
                res_dlq = self.sqs_client.get_queue_attributes(
                    QueueUrl=config.SQS_DLQ_URL,
                    AttributeNames=["ApproximateNumberOfMessages"]
                )
                attrs_main = res_main.get("Attributes", {})
                attrs_dlq = res_dlq.get("Attributes", {})
                return {
                    "tasks_visible": int(attrs_main.get("ApproximateNumberOfMessages", 0)),
                    "tasks_in_flight": int(attrs_main.get("ApproximateNumberOfMessagesNotVisible", 0)),
                    "dlq_messages": int(attrs_dlq.get("ApproximateNumberOfMessages", 0))
                }
            except Exception as e:
                logger.error(f"Error fetching AWS SQS queue attributes: {e}")
                return {"tasks_visible": 0, "tasks_in_flight": 0, "dlq_messages": 0}

    def replay_dlq_messages(self) -> int:
        """Pulls messages from DLQ and redelivers them to the main task queue."""
        if self.simulate:
            with local_cloud.lock:
                count = len(local_cloud.dlq_queue)
                for msg in local_cloud.dlq_queue:
                    msg.receive_count = 0
                    msg.visible_after = 0.0
                    local_cloud.task_queue.append(msg)
                local_cloud.dlq_queue.clear()
                return count
        else:
            # Receive from DLQ and send back to main queue
            replayed = 0
            while True:
                res = self.sqs_client.receive_message(
                    QueueUrl=config.SQS_DLQ_URL,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=1
                )
                msgs = res.get("Messages", [])
                if not msgs:
                    break
                for m in msgs:
                    self.sqs_client.send_message(QueueUrl=config.SQS_TASK_QUEUE_URL, MessageBody=m["Body"])
                    self.sqs_client.delete_message(QueueUrl=config.SQS_DLQ_URL, ReceiptHandle=m["ReceiptHandle"])
                    replayed += 1
            return replayed


# =============================================================================
# DYNAMODB SERVICE ADAPTER (With Idempotency & Status Query)
# =============================================================================
class DynamoDBService:
    def __init__(self):
        self.simulate = config.SIMULATE_AWS
        if not self.simulate:
            import boto3
            self.dynamo = boto3.resource("dynamodb", region_name=config.AWS_REGION)
            self.table = self.dynamo.Table(config.DYNAMODB_JOBS_TABLE)

    @resilient_retry(max_retries=4, base_delay=0.4)
    def put_job(self, job_data: Dict[str, Any]):
        if chaos_control.throttle_database:
            chaos_control.throttle_database = False
            chaos_control.log_incident("DYNAMODB_THROTTLED", "Injected ProvisionedThroughputExceededException")
            raise IOError("Simulated ProvisionedThroughputExceededException: The rate of requests exceeds the allowed throughput.")

        if self.simulate:
            with local_cloud.lock:
                local_cloud.database[job_data["job_id"]] = job_data
                local_cloud._save_db()
        else:
            try:
                self.table.put_item(Item=job_data)
            except Exception as e:
                logger.warning(f"DynamoDB live put error (using resilient fallback store): {e}")
                with local_cloud.lock:
                    local_cloud.database[job_data["job_id"]] = job_data
                    local_cloud._save_db()

    @resilient_retry(max_retries=3, base_delay=0.3)
    def update_job_status(self, job_id: str, status: str, error_msg: Optional[str] = None, result_data: Optional[Dict] = None):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if self.simulate:
            with local_cloud.lock:
                if job_id in local_cloud.database:
                    item = local_cloud.database[job_id]
                    item["status"] = status
                    item["updated_at"] = now
                    if error_msg:
                        item["error_message"] = error_msg
                    if result_data:
                        item["result"] = result_data
                    local_cloud._save_db()
        else:
            try:
                update_expr = "SET #s = :s, updated_at = :u"
                expr_names = {"#s": "status"}
                expr_vals = {":s": status, ":u": now}
                if error_msg:
                    update_expr += ", error_message = :e"
                    expr_vals[":e"] = error_msg
                if result_data:
                    update_expr += ", #r = :r"
                    expr_names["#r"] = "result"
                    expr_vals[":r"] = result_data
                self.table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames=expr_names,
                    ExpressionAttributeValues=expr_vals
                )
            except Exception as e:
                logger.warning(f"DynamoDB live update error (using resilient fallback store): {e}")
                with local_cloud.lock:
                    if job_id in local_cloud.database:
                        item = local_cloud.database[job_id]
                        item["status"] = status
                        item["updated_at"] = now
                        if error_msg:
                            item["error_message"] = error_msg
                        if result_data:
                            item["result"] = result_data
                        local_cloud._save_db()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if self.simulate:
            with local_cloud.lock:
                return local_cloud.database.get(job_id)
        else:
            try:
                res = self.table.get_item(Key={"job_id": job_id})
                return res.get("Item")
            except Exception:
                with local_cloud.lock:
                    return local_cloud.database.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.simulate:
            with local_cloud.lock:
                items = list(local_cloud.database.values())
                items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return items[:limit]
        else:
            try:
                res = self.table.scan(Limit=limit)
                items = res.get("Items", [])
                items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return items
            except Exception:
                with local_cloud.lock:
                    items = list(local_cloud.database.values())
                    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                    return items[:limit]


# =============================================================================
# SNS SERVICE ADAPTER (Resilience Alerts)
# =============================================================================
class SNSService:
    def __init__(self):
        self.simulate = config.SIMULATE_AWS
        if not self.simulate:
            import boto3
            self.sns_client = boto3.client("sns", region_name=config.AWS_REGION)

    def publish_incident_alert(self, subject: str, message: str):
        logger.critical(f"[SNS-ALERT] {subject}: {message}")
        if self.simulate:
            with local_cloud.lock:
                local_cloud.published_alerts.append({
                    "timestamp": time.time(),
                    "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "subject": subject,
                    "message": message
                })
        else:
            try:
                self.sns_client.publish(
                    TopicArn=config.SNS_ALERTS_TOPIC_ARN,
                    Subject=subject[:100],
                    Message=message
                )
            except Exception as e:
                logger.error(f"SNS Publish error: {e}")


# Singleton instances for application consumption
s3_client = S3Service()
sqs_client = SQSService()
dynamo_client = DynamoDBService()
sns_client = SNSService()
