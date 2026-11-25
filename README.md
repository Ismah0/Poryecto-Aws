# DocuShield AI & Resilience Hub
### Plataforma Distribuida de Ingesta, Procesamiento Asíncrono y Defensa de Caos en AWS

[![AWS CloudFormation](https://img.shields.io/badge/IaC-CloudFormation-orange.svg)](https://aws.amazon.com/cloudformation/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Resilience Tests](https://img.shields.io/badge/Resilience%20Tests-16%2F16%20Passed-brightgreen.svg)](tests/test_resilience_chaos.py)
[![Architecture](https://img.shields.io/badge/Architecture-Decoupled%20Serverless-purple.svg)](#arquitectura)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Proyecto Libre de Arquitectura Cloud AWS**  
> Cumple al 100% las 4 reglas del proyecto:
> 1. **IaC Automatizada**: Cero clics en la consola web de AWS (despliegue 100% en Python/CloudFormation).
> 2. **Pruebas de Resiliencia**: Suite automatizada y simulador interactivo de Caos ("Demuéstrame que no se rompe").
> 3. **Categoría**: Aplicación Web Distribuida (SPA + REST API + Flota de Workers).
> 4. **Alcance**: Esfuerzo equivalente a 1 mes de ingeniería cloud.

---

## 📌 Documentación y Entregables Oficiales

- 📄 **Documentación Oficial en PDF**: [docs/DocuShield_AWS_Documentacion_Oficial.pdf](docs/DocuShield_AWS_Documentacion_Oficial.pdf)
- 📝 **Documentación Técnica Completa (Markdown)**: [docs/DOCUMENTACION_OFICIAL.md](docs/DOCUMENTACION_OFICIAL.md)
- 🎤 **Guión de Presentación y Defensa (Cronometrado)**: [docs/GUION_PRESENTACION_DEFENSA.md](docs/GUION_PRESENTACION_DEFENSA.md)
- 🖥️ **Diapositivas Interactivas para la Defensa en Clase**: [docs/presentacion_diapositivas.html](docs/presentacion_diapositivas.html)

---

## 🏗️ Diagrama de Arquitectura

```
  [ Cliente SPA / Web ] ---> (1. POST) ---> [ FastAPI Web Server ]
                                               |          |
                  +----------------------------+          |
                  v (2. SSE-256 Storage)                  v (3. Encolar Tarea)
         +--------------------+                  +--------------------+
         |  Amazon S3 Raw     |                  |  Amazon SQS        |
         |  (Buckets version) |                  |  (Task Queue)      |
         +--------------------+                  +--------------------+
                                                            |
                                                            v (4. Long Poll & Visibility 30s)
                                                 +--------------------+
                                                 |  Worker Fleet      |
                                                 |  (Consumer Engine) |
                                                 +--------------------+
                                                      |          |
                 +------------------------------------+          |
                 v (5. Metadata Analizada)                       v (6. Estado Atómico)
         +--------------------+                         +--------------------+
         |  Amazon S3         |                         |  Amazon DynamoDB   |
         |  (Processed Output)|                         |  (Jobs Registry)   |
         +--------------------+                         +--------------------+
                                                                  | (Tras 3 fallos)
                                                                  v
                                                        +--------------------+
                                                        |  Amazon SQS (DLQ)  | ---> [ Amazon SNS / Alerta ]
                                                        +--------------------+
```

---

## ⚡ Guía de Despliegue Rápido (Regla 1: Cero Clics)

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/docushield-resilience-aws.git
cd docushield-resilience-aws
```

### 2. Instalar Dependencias
```bash
python -m pip install -r requirements.txt
```

### 3. Desplegar Infraestructura en AWS
```bash
# Despliegue automático a AWS mediante CloudFormation y Boto3:
python infra/deploy.py --deploy

# O si desea probar localmente sin credenciales ni cobros de AWS:
python infra/deploy.py --local
```

### 4. Ejecutar la Suite de Pruebas de Resiliencia
```bash
python tests/test_resilience_chaos.py
```
*Salida esperada:*
```text
======================================================================
   RESUMEN FINAL: 16/16 PRUEBAS DE RESILIENCIA SUPERADAS
   ESTADO: SISTEMA ALTAMENTE RESILIENTE Y TOLERANTE A FALLOS (PASSED)
======================================================================
```

### 5. Iniciar la Aplicación Web
```bash
python backend/main.py
```
Abra en su navegador: **http://localhost:8000**

---

## 🛡️ Pruebas de Resiliencia ("Demuéstrame que no se rompe")

| Experimento de Caos | Modo de Fallo | Mitigación Automatizada |
| :--- | :--- | :--- |
| **1. Muerte del Worker** | El worker colapsa violentamente a mitad del proceso. | **SQS Visibility Timeout** expira y otro worker completa la tarea. Cero pérdida de datos. |
| **2. Poison Pill Ingestion** | Archivo con bytes corruptos diseñado para causar excepción 500. | **SQS Redrive Policy** aísla la tarea en la **Dead Letter Queue (DLQ)** tras 3 intentos y dispara alerta **SNS**. La cola principal no se congela. |
| **3. Saturación DynamoDB** | Fallo 503 / Throttling de base de datos. | **Exponential Backoff + Full Jitter** descongestiona la BD y reintenta con éxito. |
| **4. Drenaje de DLQ** | Tareas en cuarentena tras corregir el error. | **DLQ Replay Utility** devuelve los mensajes a la cola principal sin intervención manual. |

---

## 💰 Análisis de Costos (1 Año Fuera de Free Tier)

| Volumen Mensual | Costo Mensual Estimado | Costo Anual Proyectado | Costo por Documento |
| :--- | :--- | :--- | :--- |
| **10,000 docs/mes** | $8.23 USD | $98.76 USD/año | $0.00082 USD |
| **100,000 docs/mes (Base)** | **$16.20 USD** | **$194.40 USD/año** | **$0.00016 USD** |
| **1,000,000 docs/mes** | $71.60 USD | $859.20 USD/año | $0.00007 USD |

> **Ahorro Arquitectónico**: Ahorro superior al **85%** respecto a soluciones monolíticas en servidores dedicados EC2 + RDS ($1,200+ USD anuales).

---

## 🧹 Destrucción de Recursos (Teardown)
Para eliminar los recursos de AWS y evitar cobros futuros:
```bash
python infra/destroy.py --force
```
