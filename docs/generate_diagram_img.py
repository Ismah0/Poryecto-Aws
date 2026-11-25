"""
Generates a high-resolution architecture diagram image for DocuShield AWS Platform.
Saved as PNG to be embedded directly into the Word document.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUTPUT_IMG = Path(__file__).resolve().parent / "diagrama_arquitectura_aws.png"

def create_architecture_diagram():
    # 1200 x 680 image with modern cloud theme
    width, height = 1200, 680
    img = Image.new("RGB", (width, height), color=(15, 23, 42)) # Slate 950
    draw = ImageDraw.Draw(img)

    # Try to load default fonts or standard system fonts
    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_sub = ImageFont.truetype("arial.ttf", 14)
        font_node_title = ImageFont.truetype("arialbd.ttf", 16)
        font_node_sub = ImageFont.truetype("arial.ttf", 12)
        font_badge = ImageFont.truetype("arialbd.ttf", 11)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_node_title = ImageFont.load_default()
        font_node_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    # Header Bar
    draw.rectangle([0, 0, width, 80], fill=(30, 41, 59)) # Slate 800
    draw.rectangle([0, 78, width, 80], fill=(234, 88, 12)) # Orange 600 accent line
    draw.text((40, 16), "DocuShield AI & Resilience Hub - Arquitectura Cloud AWS", fill=(255, 255, 255), font=font_title)
    draw.text((40, 48), "Computación Sustentable • Arquitectura Serverless Desacoplada Orientada a Eventos", fill=(148, 163, 184), font=font_sub)

    # Node definitions: (x1, y1, x2, y2, bg_color, border_color, title, subtitle, badge)
    nodes = [
        # Client
        (50, 180, 240, 280, (30, 41, 59), (99, 102, 241), "1. Cliente Web / SPA", "Ingesta de Documentos\nPresigned Ingest", "Frontend"),
        # API Server
        (330, 180, 520, 280, (30, 41, 59), (59, 130, 246), "2. FastAPI Backend", "RESTful API Server\nValidación & Hash SHA-256", "Application"),
        # S3 Raw
        (610, 130, 800, 230, (30, 41, 59), (245, 158, 11), "3. Amazon S3 Raw", "SSE-256 Storage\nVersionado & Ciclo 30d", "Storage"),
        # SQS Task Queue
        (610, 280, 800, 380, (30, 41, 59), (14, 165, 233), "4. Amazon SQS Queue", "Cola Desacoplada\nVisibility Timeout (30s)", "Messaging"),
        # Worker Fleet
        (890, 280, 1080, 380, (30, 41, 59), (16, 185, 129), "5. Worker Fleet", "Consumidores Elásticos\nExtracción de Metadatos", "Compute"),
        # DynamoDB
        (890, 460, 1080, 560, (30, 41, 59), (168, 85, 247), "6. Amazon DynamoDB", "Tabla On-Demand\nEstado e Idempotencia", "Database"),
        # S3 Processed
        (610, 460, 800, 560, (30, 41, 59), (245, 158, 11), "7. Amazon S3 Output", "Resultados JSON\nArtefactos Analizados", "Storage"),
        # SQS DLQ & SNS
        (330, 460, 520, 560, (69, 10, 10), (239, 68, 68), "8. SQS DLQ & SNS", "Dead Letter Queue\nAislamiento tras 3 fallos", "Resilience Alert"),
    ]

    # Draw Nodes
    for x1, y1, x2, y2, bg, border, title, sub, badge in nodes:
        draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=bg, outline=border, width=2)
        # Badge
        draw.rounded_rectangle([x1 + 10, y1 + 8, x1 + 85, y1 + 24], radius=6, fill=border)
        draw.text((x1 + 16, y1 + 10), badge, fill=(255, 255, 255), font=font_badge)
        # Title & Sub
        draw.text((x1 + 10, y1 + 32), title, fill=(241, 245, 249), font=font_node_title)
        draw.text((x1 + 10, y1 + 54), sub, fill=(148, 163, 184), font=font_node_sub)

    # Connections / Arrows
    def draw_arrow(p1, p2, color=(148, 163, 184), label=""):
        draw.line([p1, p2], fill=color, width=2)
        # arrowhead
        x, y = p2
        if p2[0] > p1[0]: # right
            draw.polygon([(x, y), (x - 8, y - 5), (x - 8, y + 5)], fill=color)
        elif p2[1] > p1[1]: # down
            draw.polygon([(x, y), (x - 5, y - 8), (x + 5, y - 8)], fill=color)
        elif p2[0] < p1[0]: # left
            draw.polygon([(x, y), (x + 8, y - 5), (x + 8, y + 5)], fill=color)
        elif p2[1] < p1[1]: # up
            draw.polygon([(x, y), (x - 5, y + 8), (x + 5, y + 8)], fill=color)

    # 1 -> 2
    draw_arrow((240, 230), (330, 230), (99, 102, 241))
    draw.text((250, 212), "HTTP POST", fill=(199, 210, 254), font=font_badge)

    # 2 -> 3 (S3 Raw)
    draw_arrow((425, 180), (610, 180), (245, 158, 11))
    draw.text((450, 162), "1. Guardar Raw (SSE)", fill=(253, 230, 138), font=font_badge)

    # 2 -> 4 (SQS Task)
    draw_arrow((520, 245), (610, 310), (14, 165, 233))
    draw.text((525, 260), "2. Encolar Tarea", fill=(186, 230, 253), font=font_badge)

    # 4 -> 5 (SQS -> Worker)
    draw_arrow((800, 330), (890, 330), (16, 185, 129))
    draw.text((810, 312), "3. Polling 30s", fill=(167, 243, 208), font=font_badge)

    # 5 -> 7 (Worker -> S3 Processed)
    draw_arrow((985, 380), (800, 510), (245, 158, 11))
    draw.text((820, 440), "4. Guardar Analizado", fill=(253, 230, 138), font=font_badge)

    # 5 -> 6 (Worker -> DynamoDB)
    draw_arrow((985, 380), (985, 460), (168, 85, 247))
    draw.text((995, 410), "5. Estado COMPLETED", fill=(233, 213, 255), font=font_badge)

    # 4 -> 8 (SQS Redrive -> DLQ)
    draw.line([(705, 380), (705, 420), (425, 420), (425, 460)], fill=(239, 68, 68), width=2)
    draw.polygon([(425, 460), (420, 452), (430, 452)], fill=(239, 68, 68))
    draw.text((440, 402), "Si falla 3 veces -> Redrive a DLQ & SNS Alerta", fill=(254, 202, 202), font=font_badge)

    # Footer note
    draw.rectangle([0, height - 40, width, height], fill=(30, 41, 59))
    draw.text((40, height - 28), "DocuShield Cloud Architecture • Cero consumo en reposo (Serverless Green Cloud) • AWS Well-Architected Framework", fill=(148, 163, 184), font=font_sub)

    img.save(OUTPUT_IMG, "PNG")
    print(f"[+] Architecture diagram generated at: {OUTPUT_IMG}")

if __name__ == "__main__":
    create_architecture_diagram()
