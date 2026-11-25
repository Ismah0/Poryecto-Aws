import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import config
from backend import resilience
from backend import aws_clients
from backend import worker
from backend import api

print("[+] All backend modules imported successfully!")
print(f"[*] Environment: {config.APP_ENV}")
print(f"[*] Simulate AWS: {config.SIMULATE_AWS}")
print(f"[*] Region: {config.AWS_REGION}")
