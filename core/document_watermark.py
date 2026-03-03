"""Document watermarking — apply text watermarks to PDFs and images."""

import io
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Watermarker:
    """Apply watermarks to documents on download."""

    @staticmethod
    def create_watermark_text(user: str = "", case_id: str = "") -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        parts = ["CONFIDENTIAL"]
        if case_id:
            parts.append(f"Case #{case_id}")
        if user:
            parts.append(f"Downloaded by {user}")
        parts.append(ts)
        return " - ".join(parts)

    @staticmethod
    def watermark_pdf(
        pdf_path: str,
        text: str,
        style: str = "diagonal",
        opacity: float = 0.15,
    ) -> bytes:
        """Apply text watermark to a PDF. Returns watermarked PDF bytes."""
        try:
            from PyPDF2 import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.colors import Color

            reader = PdfReader(pdf_path)
            writer = PdfWriter()

            for page in reader.pages:
                # Create watermark overlay
                w = float(page.mediabox.width)
                h = float(page.mediabox.height)
                packet = io.BytesIO()
                c = rl_canvas.Canvas(packet, pagesize=(w, h))
                c.setFillColor(Color(0.5, 0.5, 0.5, alpha=opacity))

                if style == "diagonal":
                    c.saveState()
                    c.translate(w / 2, h / 2)
                    c.rotate(45)
                    c.setFont("Helvetica", 24)
                    c.drawCentredString(0, 0, text)
                    c.restoreState()
                elif style == "header":
                    c.setFont("Helvetica", 10)
                    c.drawCentredString(w / 2, h - 20, text)
                elif style == "footer":
                    c.setFont("Helvetica", 10)
                    c.drawCentredString(w / 2, 15, text)
                elif style == "tiled":
                    c.setFont("Helvetica", 14)
                    for y in range(0, int(h), 150):
                        for x in range(0, int(w), 300):
                            c.saveState()
                            c.translate(x, y)
                            c.rotate(30)
                            c.drawString(0, 0, text)
                            c.restoreState()

                c.save()
                packet.seek(0)

                overlay_reader = PdfReader(packet)
                page.merge_page(overlay_reader.pages[0])
                writer.add_page(page)

            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()

        except ImportError as e:
            logger.error("Watermark dependencies missing: %s", e)
            # Fallback: return original file
            return Path(pdf_path).read_bytes()
        except Exception as e:
            logger.error("PDF watermarking failed: %s", e)
            return Path(pdf_path).read_bytes()

    @staticmethod
    def watermark_image(
        image_path: str,
        text: str,
        opacity: float = 0.3,
    ) -> bytes:
        """Apply text watermark to an image. Returns watermarked image bytes."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(image_path).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except (IOError, OSError):
                font = ImageFont.load_default()

            alpha = int(255 * opacity)
            # Center diagonal watermark
            draw.text(
                (img.size[0] // 4, img.size[1] // 2),
                text,
                fill=(128, 128, 128, alpha),
                font=font,
            )

            result = Image.alpha_composite(img, overlay)
            output = io.BytesIO()
            result.convert("RGB").save(output, format="PNG")
            return output.getvalue()

        except ImportError:
            logger.error("Pillow not installed for image watermarking")
            return Path(image_path).read_bytes()
        except Exception as e:
            logger.error("Image watermarking failed: %s", e)
            return Path(image_path).read_bytes()
