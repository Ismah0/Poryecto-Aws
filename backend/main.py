"""
DocuShield Server Entrypoint
============================
Launches Uvicorn server hosting the FastAPI backend and resilience worker.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from backend import config


def run():
    print(f"\n=======================================================")
    print(f"      DocuShield Resilient Web Platform Starting       ")
    print(f"=======================================================")
    print(f"[*] Environment: {config.APP_ENV.upper()}")
    print(f"[*] Simulation Mode: {config.SIMULATE_AWS}")
    print(f"[*] AWS Region: {config.AWS_REGION}")
    print(f"[*] Web Interface: http://localhost:{config.PORT}")
    print(f"[*] API Docs:      http://localhost:{config.PORT}/docs")
    print(f"=======================================================\n")

    uvicorn.run(
        "backend.api:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    run()
