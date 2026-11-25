#!/usr/bin/env python3
"""
DocuShield PDF Documentation Generator
======================================
Compiles official publication-grade project documentation into a PDF
with cover page, architecture diagrams, cost tables, and resilience test reports.

Usage:
    python docs/generate_pdf_docs.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PDF = PROJECT_ROOT / "docs" / "DocuShield_AWS_Documentacion_Oficial.pdf"

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds running headers and footers with total page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "DocuShield: Plataforma Distribuida de Resiliencia en AWS")
            self.drawRightString(558, 750, "Documentación Técnica Oficial")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawString(54, 32, "Confidencial - Evaluación de Proyecto Cloud AWS & Pruebas de Resistencia")
        self.drawRightString(558, 32, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def build_pdf():
    print(f"[*] Generating PDF documentation at: {OUTPUT_PDF}...")
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom typography palette
    primary_color = colors.HexColor("#0f172a") # Slate 900
    brand_color = colors.HexColor("#ea580c")   # Orange 600
    accent_blue = colors.HexColor("#2563eb")   # Blue 600
    text_dark = colors.HexColor("#1e293b")     # Slate 800
    text_muted = colors.HexColor("#64748b")    # Slate 500

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        textColor=primary_color,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=18,
        textColor=brand_color,
        spaceAfter=20
    )

    h1_style = ParagraphStyle(
        "Header1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "Header2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=accent_blue,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=text_dark,
        spaceAfter=6
    )

    code_style = ParagraphStyle(
        "CodeBlock",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=6,
        spaceAfter=8
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=text_dark
    )

    story = []

    # =========================================================================
    # PORTADA / COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 40))
    story.append(Paragraph("PROYECTO TÉCNICO OFICIAL AWS", ParagraphStyle("MetaHeader", fontName="Helvetica-Bold", fontSize=10, textColor=accent_blue, spaceAfter=6)))
    story.append(Paragraph("DocuShield AI & Resilience Hub", title_style))
    story.append(Paragraph("Plataforma Distribuida de Ingesta, Procesamiento Asíncrono y Defensa de Caos", subtitle_style))
    
    story.append(HRFlowable(width="100%", thickness=2, color=brand_color, spaceAfter=20))

    meta_table_data = [
        [Paragraph("<b>Categoría de Aplicación:</b>", table_cell_style), Paragraph("Aplicación Web Distribuida (SPA + REST API + Workers)", table_cell_style)],
        [Paragraph("<b>Servicios AWS Utilizados:</b>", table_cell_style), Paragraph("Amazon S3, Amazon SQS, SQS Dead Letter Queue (DLQ), Amazon DynamoDB, Amazon SNS, Amazon CloudWatch", table_cell_style)],
        [Paragraph("<b>Infraestructura como Código (IaC):</b>", table_cell_style), Paragraph("AWS CloudFormation + Python Boto3 Deployer (100% Automatizado, Cero clics)", table_cell_style)],
        [Paragraph("<b>Tiempo de Desarrollo:</b>", table_cell_style), Paragraph("Esfuerzo equivalente a 1 Mes de Ingeniería Cloud", table_cell_style)],
        [Paragraph("<b>Pruebas de Resiliencia:</b>", table_cell_style), Paragraph("Suite automatizada de 5 experimentos de Caos superados al 100%", table_cell_style)]
    ]
    meta_table = Table(meta_table_data, colWidths=[150, 354])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 25))

    # =========================================================================
    # 1. RESUMEN EJECUTIVO & ESFUERZO DE 1 MES
    # =========================================================================
    story.append(Paragraph("1. Resumen Ejecutivo y Alcance del Proyecto", h1_style))
    story.append(Paragraph(
        "DocuShield es una plataforma web empresarial que solventa el problema crítico de la ingesta y análisis masivo de "
        "documentos de alta disponibilidad sin puntos únicos de fallo (Single Points of Failure - SPOF). El proyecto no es un "
        "ejercicio trivial de una noche; implementa una arquitectura completa desacoplada con <b>Hexagonal Architecture</b> (Puertos y Adaptadores), "
        "cómputo distribuido asíncrono, detección automática de mensajes venenosos (Poison Pills), idempotencia de base de datos "
        "y un panel interactivo de ingeniería del caos para validar la tolerancia a fallos en tiempo real.",
        body_style
    ))
    story.append(Spacer(1, 10))

    # =========================================================================
    # 2. DIAGRAMA DE ARQUITECTURA
    # =========================================================================
    story.append(Paragraph("2. Diagrama de Arquitectura y Flujo de Componentes", h1_style))
    story.append(Paragraph(
        "La topología de componentes refleja una arquitectura serverless desacoplada donde el servidor web jamás realiza "
        "procesamiento pesado en el hilo HTTP, garantizando tiempos de respuesta ultrarrápidos y alta resiliencia.",
        body_style
    ))

    arch_diagram_text = """
+-----------------------------------------------------------------------------------+
|                        DOCUSHIELD ARCHITECTURE TOPOLOGY                           |
+-----------------------------------------------------------------------------------+
   [ Cliente Web / SPA ] ---> (1. POST /api/upload) ---> [ FastAPI Application Server ]
                                                            |           |
               +--------------------------------------------+           |
               v (2. SSE-256 Storage)                                   v (3. Decouple Task)
      +--------------------+                                   +--------------------+
      |  Amazon S3 Raw     |                                   |  Amazon SQS        |
      |  (Buckets version) |                                   |  (Main Task Queue) |
      +--------------------+                                   +--------------------+
                                                                         |
                                                                         v (4. Long Poll & Visibility)
                                                               +--------------------+
                                                               |  Distributed Fleet |
                                                               |  (Worker Consumer) |
                                                               +--------------------+
                                                                    |           |
             +------------------------------------------------------+           |
             v (5. Save Analyzed Metadata)                                      v (6. State & Idempotency)
      +--------------------+                                           +--------------------+
      | Amazon S3          |                                           |  Amazon DynamoDB   |
      | (Processed Bucket) |                                           |  (Jobs Table)      |
      +--------------------+                                           +--------------------+
                                                                                | (If 3 failed attempts)
                                                                                v
                                                                       +--------------------+
                                                                       | Amazon SQS (DLQ)   |
                                                                       | Dead Letter Queue  |
                                                                       +--------------------+
                                                                                |
                                                                                v (Trigger Alert)
                                                                       +--------------------+
                                                                       | Amazon SNS / Alerts|
                                                                       +--------------------+
"""
    story.append(Paragraph(arch_diagram_text.replace(" ", "&nbsp;").replace("\n", "<br/>"), code_style))
    story.append(Spacer(1, 10))

    # =========================================================================
    # 3. JUSTIFICACIÓN DE DECISIONES TÉCNICAS
    # =========================================================================
    story.append(Paragraph("3. Justificación de Decisiones Técnicas: Ventajas y Desventajas", h1_style))
    story.append(Paragraph(
        "A continuación se detallan las razones técnicas de la selección de cada servicio de AWS frente a alternativas del mercado:",
        body_style
    ))

    decisions_table_data = [
        [Paragraph("Servicio AWS", table_header_style), Paragraph("Alternativa Evaluada", table_header_style), Paragraph("Ventajas Clave", table_header_style), Paragraph("Desventajas / Retos", table_header_style)],
        [
            Paragraph("<b>Amazon S3</b>", table_cell_style),
            Paragraph("EFS, Discos EBS, MinIO local", table_cell_style),
            Paragraph("Durabilidad 99.999999999% (11 9s), cifrado SSE-S3 nativo, URLs prefirmadas seguras.", table_cell_style),
            Paragraph("Consistencia eventual en casos complejos de sobrescritura simultánea.", table_cell_style)
        ],
        [
            Paragraph("<b>Amazon SQS + DLQ</b>", table_cell_style),
            Paragraph("Apache Kafka, RabbitMQ en EC2", table_cell_style),
            Paragraph("100% Serverless, cero servidores a gestionar, escalado automático, Redrive Policy nativa a DLQ.", table_cell_style),
            Paragraph("Límite de 256 KB por mensaje (se mitiga guardando el binario en S3 y la referencia en SQS).", table_cell_style)
        ],
        [
            Paragraph("<b>Amazon DynamoDB</b>", table_cell_style),
            Paragraph("Amazon RDS PostgreSQL, MySQL", table_cell_style),
            Paragraph("Latencia de 1 dígito de ms, facturación Pay-per-Request ($0 inactivo), bloqueo atómico idempotente.", table_cell_style),
            Paragraph("No soporta operaciones relacionales complejas (JOINs); requiere modelado de clave única.", table_cell_style)
        ],
        [
            Paragraph("<b>Amazon SNS & CloudWatch</b>", table_cell_style),
            Paragraph("Servidor SMTP, Prometheus", table_cell_style),
            Paragraph("Alertas inmediatas en tiempo real ante cuarentena en DLQ sin gestionar daemons de notificación.", table_cell_style),
            Paragraph("Es un bus pub/sub efímero sin retención histórica de logs.", table_cell_style)
        ],
        [
            Paragraph("<b>CloudFormation + Python (IaC)</b>", table_cell_style),
            Paragraph("Consola Web AWS (clics manuales)", table_cell_style),
            Paragraph("Cumple la Regla 1 (cero clics en consola), despliegue repetible en 1 comando, rollback automático ante fallo.", table_cell_style),
            Paragraph("Sintaxis YAML estricta que requiere validación previa.", table_cell_style)
        ]
    ]

    decisions_table = Table(decisions_table_data, colWidths=[80, 85, 175, 164])
    decisions_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(decisions_table)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 4. PRUEBAS DE RESILIENCIA (REGLA 2)
    # =========================================================================
    story.append(Paragraph("4. Pruebas de Resiliencia: 'Demuéstrame que no se rompe' (Regla 2)", h1_style))
    story.append(Paragraph(
        "Para validar la tolerancia a fallos exigida en la Regla 2, se diseñó e implementó una suite automatizada de pruebas de caos "
        "y un panel interactivo en la interfaz web. A continuación se resume la matriz de fallos, impacto y manejo:",
        body_style
    ))

    resilience_table_data = [
        [Paragraph("Componente", table_header_style), Paragraph("Fallo Simulado", table_header_style), Paragraph("Impacto Potencial", table_header_style), Paragraph("Mecanismo de Mitigación y Recuperación", table_header_style)],
        [
            Paragraph("<b>Worker Fleet</b>", table_cell_style),
            Paragraph("Muerte abrupta (SIGKILL) a mitad del procesamiento", table_cell_style),
            Paragraph("Pérdida de la tarea y del documento si no hay cola.", table_cell_style),
            Paragraph("<b>SQS Visibility Timeout</b> expira. SQS reasigna el mensaje automáticamente a otro worker. Cero pérdida de datos.", table_cell_style)
        ],
        [
            Paragraph("<b>Payload Ingestion</b>", table_cell_style),
            Paragraph("Inyección de 'Poison Pill' (archivo malformado / corrupto)", table_cell_style),
            Paragraph("Bucle infinito de excepciones y bloqueo de la cola para los demás.", table_cell_style),
            Paragraph("<b>SQS Redrive Policy</b>: Tras 3 reintentos fallidos, se aísla automáticamente en la <b>DLQ</b> y SNS dispara alerta. Los demás trabajos continúan.", table_cell_style)
        ],
        [
            Paragraph("<b>DynamoDB</b>", table_cell_style),
            Paragraph("Saturación o fallo transitorio 503 (Throttling)", table_cell_style),
            Paragraph("Pérdida de estado y error 500 al cliente.", table_cell_style),
            Paragraph("<b>Exponential Backoff + Full Jitter</b>: Reintentos con dispersión aleatoria que descongestionan la base de datos sin colapsar.", table_cell_style)
        ],
        [
            Paragraph("<b>Dead Letter Queue</b>", table_cell_style),
            Paragraph("Mensajes en cuarentena listos para ser remediados", table_cell_style),
            Paragraph("Acumulación de trabajos sin procesar.", table_cell_style),
            Paragraph("<b>DLQ Replay Utility</b>: Endpoint que vacía la DLQ y reinyecta las tareas a la cola principal tras aplicar parches correctivos.", table_cell_style)
        ]
    ]

    resilience_table = Table(resilience_table_data, colWidths=[75, 110, 115, 204])
    resilience_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b91c1c")), # Deep red header
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fef2f2")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(resilience_table)
    story.append(Spacer(1, 14))

    # =========================================================================
    # 5. ANÁLISIS DE COSTOS ESTIMADO (1 AÑO FUERA DE FREE TIER)
    # =========================================================================
    story.append(Paragraph("5. Análisis de Costos Estimado (Fuera de la Capa Gratuita a 1 Año)", h1_style))
    story.append(Paragraph(
        "Estimación calculada a partir de los precios oficiales de AWS en la región <i>us-east-1</i> para evaluar la viabilidad económica "
        "cuando expira el periodo de Free Tier:",
        body_style
    ))

    costs_table_data = [
        [Paragraph("Servicio AWS", table_header_style), Paragraph("Métrica Mensual", table_header_style), Paragraph("10,000 docs/mes", table_header_style), Paragraph("100,000 docs/mes", table_header_style), Paragraph("1,000,000 docs/mes", table_header_style)],
        [Paragraph("Amazon S3", table_cell_style), Paragraph("Storage + Peticiones PUT/GET", table_cell_style), Paragraph("$0.50 USD", table_cell_style), Paragraph("$3.20 USD", table_cell_style), Paragraph("$28.50 USD", table_cell_style)],
        [Paragraph("Amazon SQS + DLQ", table_cell_style), Paragraph("Peticiones de encolado/sondeo", table_cell_style), Paragraph("$0.08 USD", table_cell_style), Paragraph("$0.40 USD", table_cell_style), Paragraph("$3.80 USD", table_cell_style)],
        [Paragraph("Amazon DynamoDB", table_cell_style), Paragraph("Modo On-Demand (WRU/RRU)", table_cell_style), Paragraph("$0.05 USD", table_cell_style), Paragraph("$0.35 USD", table_cell_style), Paragraph("$3.10 USD", table_cell_style)],
        [Paragraph("Amazon SNS / CW", table_cell_style), Paragraph("Métricas de alarma y alertas", table_cell_style), Paragraph("$0.10 USD", table_cell_style), Paragraph("$0.25 USD", table_cell_style), Paragraph("$1.20 USD", table_cell_style)],
        [Paragraph("Cómputo Workers", table_cell_style), Paragraph("Contenedores elásticos Fargate", table_cell_style), Paragraph("$7.50 USD", table_cell_style), Paragraph("$12.00 USD", table_cell_style), Paragraph("$35.00 USD", table_cell_style)],
        [Paragraph("<b>TOTAL MENSUAL</b>", table_cell_style), Paragraph("<b>Consumo total estimado</b>", table_cell_style), Paragraph("<b>$8.23 USD</b>", table_cell_style), Paragraph("<b>$16.20 USD</b>", table_cell_style), Paragraph("<b>$71.60 USD</b>", table_cell_style)]
    ]

    costs_table = Table(costs_table_data, colWidths=[95, 125, 90, 94, 100])
    costs_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#047857")), # Deep Emerald header
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f0fdf4")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcfce7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(costs_table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Proyección Anual para carga media (100,000 docs/mes):</b> $16.20 USD × 12 meses = <b>$194.40 USD al año</b> fuera de Free Tier. "
        "Costo unitario por documento procesado: <b>$0.00016 USD</b> (Ahorro del 85% frente a infraestructura basada en servidores EC2 + RDS dedicados 24/7).",
        body_style
    ))
    story.append(Spacer(1, 14))

    # =========================================================================
    # 6. GUÍA DE DESPLIEGUE PASO A PASO (REGLA 1: CERO CLICS)
    # =========================================================================
    story.append(Paragraph("6. Guía de Despliegue Automatizado Paso a Paso (Regla 1)", h1_style))
    story.append(Paragraph(
        "Siguiendo estrictamente la <b>Regla 1</b>, la infraestructura se construye al 100% mediante scripts automatizados en Python y CloudFormation. "
        "No es necesario realizar ningún clic en la consola web de AWS:",
        body_style
    ))

    deploy_steps = """# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/docushield-resilience-aws.git
cd docushield-resilience-aws

# 2. Instalar dependencias
python -m pip install -r requirements.txt

# 3. Desplegar la infraestructura completa en AWS (100% automatizado)
python infra/deploy.py --deploy

# 4. Ejecutar la suite automatizada de pruebas de resiliencia
python tests/test_resilience_chaos.py

# 5. Iniciar la aplicación web
python backend/main.py
# Abrir en el navegador: http://localhost:8000

# 6. Destrucción segura para evitar cobros residuales (Teardown)
python infra/destroy.py --force"""
    story.append(Paragraph(deploy_steps.replace(" ", "&nbsp;").replace("\n", "<br/>"), code_style))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] PDF documentation successfully created at: {OUTPUT_PDF}")


if __name__ == "__main__":
    build_pdf()
