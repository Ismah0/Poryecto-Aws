#!/usr/bin/env bash
# ==============================================================================
# DocuShield Automated Deployment Script (Bash / POSIX)
# ==============================================================================
set -e

echo "=== DocuShield: Despliegue Automatizado de Infraestructura AWS ==="

# Check Python installation
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[-] Error: Python 3 no está instalado en este sistema."
    exit 1
fi

PY_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PY_CMD="python"
fi

# Run the python infrastructure deployer
$PY_CMD infra/deploy.py --deploy "$@"
