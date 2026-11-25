# Guión Oficial de Presentación y Defensa del Proyecto
## DocuShield AI & Resilience Hub en Amazon Web Services
**Duración Total Estimada:** 8 a 10 minutos (5 min Demo en Vivo + 3-5 min Explicación Técnica)  

---

## ESTRUCTURA DE LA DEFENSA

```
 ┌───────────────────────────────────────────────────────────────┐
 │               CRONOGRAMA DE DEFENSA EN CLASE                  │
 ├───────────────────────────────┬───────────────────────────────┤
 │  PARTE 1: DEMOSTRACIÓN EN VIVO│  PARTE 2: EXPLICACIÓN TÉCNICA │
 │         (5 Minutos)           │        (3 a 5 Minutos)        │
 ├───────────────────────────────┼───────────────────────────────┤
 │ • 0:00-1:00 Ingesta Nominal   │ • 0:00-1:30 Arquitectura AWS  │
 │ • 1:00-2:30 Crash de Worker   │ • 1:30-3:00 Justificación Dec.│
 │ • 2:30-4:00 Poison Pill & DLQ │ • 3:00-4:15 Análisis Costos   │
 │ • 4:00-5:00 Drenaje DLQ       │ • 4:15-5:00 Cierre y Preguntas│
 └───────────────────────────────┴───────────────────────────────┘
```

---

# PARTE 1: DEMOSTRACIÓN EN VIVO (5 MINUTOS)

### Minuto 0:00 - 1:00: Bienvenida e Ingesta Nominal de Documentos
- **Qué decir:**
  > *"Buenos días profesor y compañeros. Hoy les presentamos **DocuShield**, una plataforma web distribuida y tolerante a fallos desarrollada en Amazon Web Services que representa el esfuerzo de un mes de diseño de arquitectura cloud. La plataforma realiza ingesta, extracción de metadatos y análisis de integridad documental sin puntos únicos de fallo."*
- **Qué hacer en pantalla:**
  1. Mostrar la interfaz web en `http://localhost:8000`.
  2. Hacer clic en **"Cargar Documento de Prueba"** (o arrastrar un archivo de texto).
  3. Señalar en la tabla cómo el estado pasa de `QUEUED` a `PROCESSING` y finalmente a `COMPLETED` en milisegundos.
  4. Abrir el modal de **"Ver Detalle"** y mostrar el hash SHA-256 generado y las métricas extraídas en Amazon S3 y DynamoDB.
- **Mensaje clave:** El servidor web jamás se congela porque desacopla el trabajo mediante Amazon SQS.

---

### Minuto 1:00 - 2:30: Prueba de Resiliencia 1 — Caída Abrupta del Worker (Crash mid-flight)
- **Qué decir:**
  > *"Ahora pasamos a responder la Regla 2: **'Demuéstrame que no se rompe'**. ¿Qué ocurriría si un worker de cómputo se apaga violentamente o sufre un fallo de energía a mitad del procesamiento de un documento crítico? En arquitecturas tradicionales, el archivo se perdería. En DocuShield, no."*
- **Qué hacer en pantalla:**
  1. En el panel de **Laboratorio de Caos**, hacer clic en el botón rojo: **"Forzar Muerte en Próximo Job"**.
  2. Subir un nuevo archivo.
  3. Mostrar en la consola de incidentes en vivo: `[WORKER_CRASH_SIMULATION] Worker crashed intentionally while processing job...`
  4. Explicar al profesor:
     > *"El worker murió sin enviar el acuse a SQS. El mensaje quedó en el limbo. Pero gracias al parámetro `VisibilityTimeout` de Amazon SQS, el temporizador expira, el mensaje vuelve a estar visible en la cola y un worker sano lo toma y lo completa exitosamente. Cero pérdida de datos."*
  5. Mostrar en la tabla de DynamoDB cómo el trabajo finaliza con estado `COMPLETED`.

---

### Minuto 2:30 - 4:00: Prueba de Resiliencia 2 — Mensaje Malicioso / Poison Pill y Dead Letter Queue (DLQ)
- **Qué decir:**
  > *"El segundo reto de resiliencia: ¿Qué ocurre si un usuario sube un archivo con binarios corruptos o un payload venenoso diseñado para tumbar el algoritmo? Si un worker intenta procesarlo una y otra vez, la cola entera se congelaría por inanición (Queue Starvation)."*
- **Qué hacer en pantalla:**
  1. Hacer clic en el botón amarillo: **"Inyectar Mensaje Venenoso (Poison Pill)"**.
  2. Ver cómo el worker intenta procesarlo 3 veces consecutivas (`Attempt 1/3`, `2/3`, `3/3`).
  3. Mostrar en la interfaz cómo el nodo de la **Dead Letter Queue (DLQ)** se ilumina en rojo y el trabajo cambia a estado `DLQ_QUARANTINE`.
  4. Mostrar en la consola la alerta emitida por **Amazon SNS**:
     > *"DocuShield aplicó la política de Redrive: al tercer fallo, el mensaje venenoso fue extraído y aislado en la DLQ, evitando que consuma más CPU y permitiendo que los trabajos de los demás usuarios sigan fluyendo con normalidad."*

---

### Minuto 4:00 - 5:00: Drenaje de DLQ (Redrive) y Cierre de la Demo
- **Qué decir:**
  > *"Una vez que el equipo de soporte analiza el error o despliega un parche, no descartamos los datos."*
- **Qué hacer en pantalla:**
  1. Hacer clic en **"Drenar y Reprocesar DLQ"**.
  2. Mostrar cómo el contador de la DLQ vuelve a `0` y los mensajes regresan a la cola principal listos para un reintento controlado.
  3. Concluir la demo: *"Con esto demostramos en vivo que el sistema absorbe caídas de servidores, aísla ataques o errores de datos y se auto-recupera."*

---

# PARTE 2: EXPLICACIÓN TÉCNICA (3 A 5 MINUTOS)

### Minuto 0:00 - 1:30: Recorrido del Diagrama de Arquitectura y Flujo de Datos
- **Qué decir proyectando la diapositiva de arquitectura:**
  > *"Nuestra arquitectura sigue el patrón de microservicios asíncronos y desacoplados del Well-Architected Framework:*
  > 1. *El cliente interactúa con un API REST en FastAPI que actúa como compuerta.*
  > 2. *Los binarios se almacenan directamente en **Amazon S3** con cifrado `SSE-256` y ciclo de vida de limpieza automática a 30 días.*
  > 3. *La comunicación entre la API y el cómputo está 100% desacoplada mediante **Amazon SQS**.*
  > 4. *La flota de workers consume tareas de forma elástica; si el tráfico aumenta, basta con añadir más workers sin modificar la base de datos ni el frontend.*
  > 5. *El estado y la deduplicación (idempotencia mediante hash SHA-256) se controlan en **Amazon DynamoDB**.*
  > 6. *Cualquier anomalía es monitoreada por **CloudWatch** y notificada al instante vía **Amazon SNS**."*

---

### Minuto 1:30 - 3:00: Justificación de Decisiones Técnicas (Por qué estos servicios y no otros)
- **Qué decir:**
  > *"Evaluamos rigurosamente alternativas antes de seleccionar cada servicio:*
  > - ***Amazon S3 vs EBS/EFS:** S3 nos entrega durabilidad de 11 nueves (99.999999999%) y URLs prefirmadas a una fracción del costo de un sistema de archivos montado.*
  > - ***Amazon SQS vs RabbitMQ o Apache Kafka:** Kafka y RabbitMQ requerirían aprovisionar y mantener clústeres de servidores EC2 dedicados, con costos fijos 24/7 y parches continuos. SQS es 100% serverless, con costo cero en reposo y configuración nativa de DLQ.*
  > - ***Amazon DynamoDB vs RDS PostgreSQL:** Como el ciclo de vida de una tarea es clave-valor puro (`job_id`), una base de datos relacional colapsaría si 10,000 workers intentan abrir conexiones simultáneas. DynamoDB en modo `On-Demand` escala a millones de peticiones por segundo con latencias de un solo dígito de milisegundo.*
  > - ***Infraestructura como Código (Regla 1):** Cumplimos al 100% la prohibición de crear recursos con clics en la consola web. Toda la infraestructura está declarada en CloudFormation y se despliega con un script en Python (`infra/deploy.py`), garantizando reproducibilidad total y rollback automático ante cualquier fallo."*

---

### Minuto 3:00 - 4:15: Análisis de Costos Fuera de la Capa Gratuita a 1 Año
- **Qué decir proyectando la tabla de costos:**
  > *"Hicimos el análisis financiero con la Calculadora de Precios de AWS para cuando expire el Free Tier:*
  > - *Para una carga mensual de **10,000 documentos**, el costo total es de apenas **\$8.23 USD al mes**.*
  > - *Para una carga empresarial media de **100,000 documentos al mes**, el costo es de **\$16.20 USD al mes**, lo que equivale a **\$194.40 USD al año**.*
  > - *El costo unitario resultante es de **\$0.00016 USD por documento analizado**.*
  > - *Comparado con una solución basada en servidores EC2 dedicados y un clúster RDS que costaría más de \$1,200 USD anuales, nuestra arquitectura serverless genera un **ahorro superior al 85%**, pagando estrictamente por lo que se procesa."*

---

### Minuto 4:15 - 5:00: Cierre y Espacio para Preguntas
- **Qué decir:**
  > *"En conclusión, DocuShield demuestra que una arquitectura moderna en la nube no solo debe ser funcional, sino intrínsecamente resistente al caos. El código fuente completo, los scripts IaC y la documentación en PDF están disponibles en el repositorio. Quedamos atentos a cualquier pregunta técnica del profesor. Muchas gracias."*
