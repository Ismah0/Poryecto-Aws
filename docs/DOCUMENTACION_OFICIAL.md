# DocuShield AI & Resilience Hub
## Plataforma Distribuida de Ingesta, Procesamiento y Defensa de Caos en AWS
**Documentación Técnica Oficial del Proyecto**  
*Categoría: Aplicación Web Distribuida Empresarial*  
*Tiempo Estimado de Desarrollo: 1 Mes de Ingeniería de Software Cloud*  

---

## 1. Resumen Ejecutivo y Alcance del Proyecto

**DocuShield** es una plataforma web distribuida diseñada bajo los más rigurosos estándares de resiliencia del *AWS Well-Architected Framework* (Especialmente los pilares de **Fiabilidad**, **Seguridad** y **Eficiencia de Rendimiento**). 

El sistema resuelve un problema crítico en arquitecturas empresariales: **la ingesta masiva y análisis asíncrono de documentos e imágenes sin puntos únicos de fallo (SPOF)**. Implementa patrones arquitectónicos avanzados:
- **Desacoplamiento asíncrono con Colas SQS**: Evita la saturación del servidor web y amortigua picos repentinos de tráfico.
- **Aislamiento de Mensajes Venenosos con Dead Letter Queue (DLQ)**: Evita que peticiones maliciosas o corruptas colapsen los workers o bloqueen a otros usuarios.
- **Idempotencia y Estado Atómico en Amazon DynamoDB**: Previene doble procesamiento ante reintentos automáticos de la red.
- **Reintentos Resilientes con Exponential Backoff y Full Jitter**: Mitiga caídas transitorias y saturación de base de datos.
- **Laboratorio Interactivo de Ingeniería del Caos**: Permite simular caídas de workers, fallos de storage e inyecciones de payloads corruptos directamente desde la interfaz web o consola CLI.

---

## 2. Diagrama de Arquitectura y Flujo de Componentes

### 2.1 Diagrama de Bloques de Arquitectura

```
 +-------------------------------------------------------------------------------+
 |                              DOCUSHIELD ARCHITECTURE                          |
 +-------------------------------------------------------------------------------+

       [ Cliente Web / SPA ]
         (Dashboard HTML5/JS)
                 |
                 |  1. POST /api/upload (Documento)
                 v
       +--------------------+
       |  FastAPI Backend   | <---------+  API REST & Métricas
       |  (Application Hub) |           |  (Health, Jobs, Chaos Controls)
       +--------------------+           |
            |            |              |
 2. Subida  |            | 3. Encolar   |
    Segura  |            |    Tarea     |
            v            v              |
     +------------+  +----------------------+
     | Amazon S3  |  | Amazon SQS           |
     | Raw Bucket |  | (Main Task Queue)    |
     +------------+  +----------------------+
                           |
                           | 4. Polling & Visibility Timeout (30s)
                           v
                     +----------------------+
                     | Distributed Workers  |
                     | (Consumer Fleet)     |
                     +----------------------+
                           |           |
        5. Almacena        |           | 6. Estado Atómico
           Resultado       |           |    & Idempotencia
           Analizado       v           v
     +------------+  +----------------------+  (Fallo tras 3 reintentos)
     | Amazon S3  |  | Amazon DynamoDB      | ------------------------+
     | Processed  |  | (Jobs Registry Table)|                          |
     +------------+  +----------------------+                          v
                                                              +------------------+
                                                              | Amazon SQS (DLQ) |
                                                              | Dead Letter Queue|
                                                              +------------------+
                                                                       |
                                                                       | Dispara
                                                                       v
                                                              +------------------+
                                                              | Amazon SNS / CW  |
                                                              | Alerta Incidente |
                                                              +------------------+
```

### 2.2 Flujo de Datos Detallado Paso a Paso:
1. **Ingesta**: El usuario arrastra un archivo en el frontend web. El backend calcula su hash SHA-256 para verificación de integridad y control de idempotencia.
2. **Persistencia Raw**: El documento binario original se almacena en el bucket `docushield-raw-*` con cifrado en reposo `AES256` y versionado activo.
3. **Desacoplamiento SQS**: Se publica un mensaje ligero en la cola principal `docushield-task-queue`. El backend responde inmediatamente al usuario con estado `QUEUED`, sin bloquear el hilo HTTP.
4. **Consumo por Workers**: La flota de workers distribuidos realiza *long polling* seguro sobre SQS. Al tomar un mensaje, SQS activa el `VisibilityTimeout` de 30 segundos para ocultar el mensaje a otros workers mientras se procesa.
5. **Transformación y Análisis**: El worker descarga el archivo de S3, extrae métricas estadísticas (palabras, líneas, distribución de caracteres, verificación de firmas de seguridad).
6. **Almacenamiento de Resultados**: El artefacto analizado se guarda en el bucket `docushield-processed-*` en formato JSON enriquecido.
7. **Actualización de Estado**: El worker actualiza la tabla de DynamoDB a `COMPLETED` y borra el mensaje de SQS (`delete_message`), confirmando que la transacción concluyó con éxito.

---

## 3. Justificación de Decisiones Técnicas: ¿Por qué estos servicios?

| Servicio Elegido | Alternativas Evaluadas | Ventajas Clave | Desventajas / Limitaciones | Justificación de la Elección |
| :--- | :--- | :--- | :--- | :--- |
| **Amazon S3** | Amazon EFS, EBS, MinIO local | • Durabilidad extrema del 99.999999999% (11 nueves).<br>• Cifrado nativo Server-Side SSE-S3.<br>• URLs prefirmadas para subida directa sin sobrecargar servidores. | • Consistencia eventual tras sobrescrituras concurrentes complejas.<br>• Costo por peticiones PUT/GET si no se agrupan. | Es el estándar de oro en la nube para almacenamiento de archivos no estructurados. Elimina la necesidad de aprovisionar discos duros o servidores de archivos. |
| **Amazon SQS + DLQ** | Apache Kafka, RabbitMQ en EC2, AWS Kinesis | • Completamente Serverless (0 mantenimiento de servidores).<br>• Escalabilidad elástica infinita sin administración de clústeres.<br>• Política de Redrive integrada a Dead Letter Queue en 3 clics o líneas IaC. | • Límite de carga útil de 256 KB por mensaje (se mitiga guardando el binario en S3 y solo la referencia en SQS).<br>• Orden FIFO no garantizado en colas estándar (para este caso no se requiere orden estricto). | Para un sistema de procesamiento asíncrono por tareas, Kafka o RabbitMQ introducen una sobrecarga de costos y mantenimiento de infraestructura innecesaria. SQS ofrece desacoplamiento instantáneo con costo cero en reposo. |
| **Amazon DynamoDB** | Amazon RDS PostgreSQL, MySQL, MongoDB | • Latencia de milisegundos de un solo dígito.<br>• Modelo de facturación `PAY_PER_REQUEST` (On-Demand: \$0 cuando no hay tráfico).<br>• Índices Secundarios Globales (GSI) para consultar por estado (`QUEUED`, `PROCESSING`, `COMPLETED`). | • Consultas complejas (JOINs) no están soportadas nativamente.<br>• Curva de aprendizaje en diseño de modelos de clave única (Single Table Design). | El ciclo de vida de un trabajo (`job_id`) es clave-valor puro. DynamoDB soporta millones de escrituras concurrentes sin preocuparse por caídas de base de datos relacional por exceso de conexiones. |
| **Amazon SNS & CloudWatch** | Servidor de correo SMTP, Prometheus autohospedado | • Notificación instantánea a múltiples suscriptores (Email, SMS, Webhooks Lambda).<br>• Alarmas automáticas ante métricas críticas (mensajes en DLQ > 0). | • No almacena historial de mensajes (es un bus pub/sub efímero). | Proporciona alertamiento en tiempo real inmediato cuando se detecta una anomalía de resiliencia en la DLQ. |
| **CloudFormation & Python Boto3 (IaC)** | Terraform, Pulumi, Consola Web manual | • Sintaxis nativa declarativa de AWS sin dependencias de estado remoto (.tfstate en S3 externo).<br>• Rollback automático en caso de fallo durante el despliegue.<br>• Cumple al 100% la Regla 1 (cero clics en consola web). | • Sintaxis YAML detallada.<br>• Tiempos de actualización moderados al validar recursos. | Garantiza que cualquier evaluador pueda clonar el repositorio y levantar la infraestructura en minutos con un solo comando. |

---

## 4. Pruebas de Resiliencia: "Demuéstrame que no se rompe" (Regla 2)

El sistema incluye una sección y suite automatizada de pruebas de caos (`tests/test_resilience_chaos.py`) que somete a la infraestructura a 5 escenarios críticos de fallo:

### 4.1 Matriz de Fallos, Impacto y Mitigación

| Componente | Modo de Fallo Simulado | Impacto Potencial (Blast Radius) | Mecanismo de Detección | Mitigación Automatizada y Recuperación |
| :--- | :--- | :--- | :--- | :--- |
| **Worker Fleet** | **Caída Abrupta del Worker** (Crash mid-flight por SIGKILL o fallo de energía) | Tarea interrumpida a la mitad; si no se maneja, el mensaje se perdería para siempre. | Expiración del `VisibilityTimeout` (30s) en Amazon SQS. | **SQS redeliver automático**: Al no recibir el acuse (`delete_message`), SQS devuelve el mensaje a la cola. Otro worker lo toma y lo completa. La clave SHA-256 en DynamoDB previene duplicados. |
| **Payload Ingestion** | **Poison Pill / Mensaje Malformado** (Documento con bytes corruptos o exploit) | Un worker entraría en bucle infinito de excepciones, consumiendo CPU y bloqueando la cola. | El worker captura la excepción irrecuperable y no elimina el mensaje. | **SQS Redrive Policy + DLQ**: Tras 3 intentos fallidos (`maxReceiveCount: 3`), SQS aísla el mensaje en la Dead Letter Queue. DynamoDB actualiza a `DLQ_QUARANTINE` y SNS envía una alerta. **El resto de las tareas siguen procesándose sin demora.** |
| **Amazon DynamoDB** | **Saturación / Throttling** (`ProvisionedThroughputExceededException` o corte transitorio) | Error 500 al guardar el estado del trabajo, perdiendo la trazabilidad. | Detección del código de error 503 / ClientError por el SDK. | **Exponential Backoff con Full Jitter**: El decorador `@resilient_retry` calcula esperas aleatorias crecientes ($T = \text{random}(0, \min(T_{max}, T_{base} \times 2^{intento}))$), evitando la tormenta de reintentos concurrentes (*Thundering Herd*). |
| **Amazon S3** | **Caída Temporal de Subida** (`ServiceUnavailableException`) | Pérdida del artefacto final analizado. | Captura de excepción en capa de storage. | Reintento automático transparente con 3 intentos y buffer de contingencia local. |
| **Dead Letter Queue** | **Recuperación Post-Incidente** (Mensajes en cuarentena listos para ser corregidos) | Datos acumulados sin procesar. | Métrica de CloudWatch `ApproximateNumberOfMessagesVisible > 0`. | **DLQ Redrive Utility**: Endpoint y botón en interfaz `/api/dlq/replay` que drena la DLQ e inyecta los mensajes de vuelta a la cola una vez corregido el error. |

---

## 5. Análisis de Costos Estimado (Fuera de la Capa Gratuita a 1 Año)

Estimación detallada basada en la **Calculadora Oficial de Precios de AWS** (Región: `us-east-1`, moneda: USD):

### 5.1 Estimación por Volumen Mensual

| Servicio AWS | Métrica de Consumo Mensual | Costo Estimado (10,000 docs/mes) | Costo Estimado (100,000 docs/mes) | Costo Estimado (1,000,000 docs/mes) |
| :--- | :--- | :--- | :--- | :--- |
| **Amazon S3 (Raw + Processed)** | 20 GB de almacenamiento promedio + 40,000 peticiones PUT/GET | \$0.50 USD | \$3.20 USD | \$28.50 USD |
| **Amazon SQS + DLQ** | 200,000 peticiones de sondeo y envío | \$0.08 USD | \$0.40 USD | \$3.80 USD |
| **Amazon DynamoDB** | Modo On-Demand (20,000 WRU + 40,000 RRU) | \$0.05 USD | \$0.35 USD | \$3.10 USD |
| **Amazon SNS & CloudWatch** | Métricas de colas y 100 alertas por mes | \$0.10 USD | \$0.25 USD | \$1.20 USD |
| **Cómputo (Fargate / EC2 Worker)** | 1 contenedor ligero de procesamiento (0.25 vCPU, 0.5 GB RAM) | \$7.50 USD | \$12.00 USD (Auto-escalado) | \$35.00 USD (3 instancias) |
| **Subtotal Mensual** | | **\$8.23 USD** | **\$16.20 USD** | **\$71.60 USD** |

### 5.2 Proyección a 1 Año Fuera de la Capa Gratuita (Free Tier Expirado):
- **Carga Media de Trabajo (100,000 documentos/mes)**:
  $$\text{Costo Anual} = \$16.20 \times 12 = \mathbf{\$194.40\text{ USD/año}}$$
- **Eficiencia Económica**:
  El costo por documento procesado y almacenado de forma redundante y resiliente es de aproximadamente **\$0.00016 USD**, lo que representa un ahorro de más del 85% comparado con arquitecturas tradicionales basadas en servidores EC2 dedicados con bases de datos RDS aprovisionadas 24/7.

---

## 6. Guía de Despliegue Paso a Paso desde Cero (Regla 1)

> [!IMPORTANT]
> Siguiendo la **Regla 1**, toda la infraestructura se construye mediante scripts automatizados en Python y plantillas de CloudFormation. No es necesario realizar ningún clic en la consola web de AWS.

### Requisitos Previos:
- Python 3.10+ instalado.
- Git instalado.
- Cuenta de AWS (Credenciales configuradas con `aws configure` o variables de entorno `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`).
  *(Nota: Si no se configuran credenciales, el sistema ejecuta automáticamente su simulador local de alta fidelidad sin generar ningún cobro).*

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/docushield-resilience-aws.git
cd docushield-resilience-aws
```

### Paso 2: Instalar Dependencias
```bash
python -m pip install -r requirements.txt
```

### Paso 3: Desplegar la Infraestructura en AWS (Cero Clics)
Ejecute el script maestro de infraestructura. Este script valida la plantilla, levanta el stack de CloudFormation y genera automáticamente el archivo `.env`:
```bash
# En Linux / macOS / Bash:
python infra/deploy.py --deploy

# O mediante el script Bash:
./infra/deploy.sh

# O en Windows PowerShell:
.\infra\deploy.ps1 -Deploy
```

### Paso 4: Ejecutar la Suite de Pruebas de Resiliencia
Antes de abrir la aplicación web, verifique que la infraestructura resiste los fallos de caos:
```bash
python tests/test_resilience_chaos.py
```
*(Debe mostrar 16/16 pruebas superadas).*

### Paso 5: Iniciar la Aplicación Web
```bash
python backend/main.py
```
Abra su navegador en: `http://localhost:8000`

### Paso 6: Destrucción de la Infraestructura (Teardown)
Para evitar cualquier cobro posterior al finalizar la defensa o evaluación del proyecto:
```bash
python infra/destroy.py --force
```

---

## 7. Estructura del Repositorio de Git

```
docushield-resilience-aws/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Pipeline de integración continua (Lint + Tests)
├── backend/
│   ├── __init__.py
│   ├── config.py                      # Configuración centralizada y lectura de .env
│   ├── aws_clients.py                 # Puertos y adaptadores (S3, SQS, DynamoDB, SNS)
│   ├── resilience.py                  # Exponential backoff, Circuit breaker, Chaos manager
│   ├── worker.py                      # Consumidor asíncrono con manejo de fallos
│   ├── api.py                         # FastAPI endpoints REST, ingesta y caos
│   └── main.py                        # Punto de entrada del servidor Uvicorn
├── frontend/
│   └── index.html                     # Dashboard SPA moderno con Tailwind y controles de caos
├── infra/
│   ├── cloudformation-template.yaml   # Plantilla IaC (S3, SQS, DLQ, DynamoDB, SNS)
│   ├── deploy.py                      # Script de automatización IaC en Python
│   ├── destroy.py                     # Script de borrado seguro y vaciado de buckets
│   ├── deploy.sh                      # Script Bash para despliegue
│   └── deploy.ps1                     # Script PowerShell para despliegue
├── tests/
│   ├── __init__.py
│   ├── test_imports.py                # Verificación de integridad de módulos
│   └── test_resilience_chaos.py       # Suite automatizada de pruebas de resistencia
├── docs/
│   ├── DOCUMENTACION_OFICIAL.md       # Documento técnico completo
│   ├── generate_pdf_docs.py           # Generador del PDF oficial con ReportLab
│   └── GUION_PRESENTACION_DEFENSA.md  # Guión cronometrado para la defensa en clase
├── .gitignore
├── requirements.txt
└── README.md                          # Portada del repositorio para GitHub/GitLab
```
