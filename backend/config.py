"""
DocuShield System Configuration
Reads environment variables with fallback defaults.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Read .env file without requiring external dependencies
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass

APP_ENV = os.getenv("APP_ENV", "local")
SIMULATE_AWS = os.getenv("SIMULATE_AWS", "true").lower() in ("true", "1", "yes")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Amazon S3
S3_RAW_BUCKET = os.getenv("S3_RAW_BUCKET", "docushield-local-raw")
S3_PROCESSED_BUCKET = os.getenv("S3_PROCESSED_BUCKET", "docushield-local-processed")

# Amazon SQS
SQS_TASK_QUEUE_URL = os.getenv("SQS_TASK_QUEUE_URL", "http://localhost:8000/mock-sqs/tasks")
SQS_DLQ_URL = os.getenv("SQS_DLQ_URL", "http://localhost:8000/mock-sqs/dlq")

# Amazon DynamoDB
DYNAMODB_JOBS_TABLE = os.getenv("DYNAMODB_JOBS_TABLE", "docushield-local-jobs")

# Amazon SNS
SNS_ALERTS_TOPIC_ARN = os.getenv("SNS_ALERTS_TOPIC_ARN", "arn:aws:sns:local:000000000000:docushield-alerts")

# Server Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Local Data Directories (used in simulation mode)
LOCAL_DATA_DIR = PROJECT_ROOT / "data"
LOCAL_RAW_DIR = LOCAL_DATA_DIR / "s3_raw"
LOCAL_PROCESSED_DIR = LOCAL_DATA_DIR / "s3_processed"
LOCAL_DB_FILE = LOCAL_DATA_DIR / "jobs_database.json"

for d in [LOCAL_DATA_DIR, LOCAL_RAW_DIR, LOCAL_PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)
