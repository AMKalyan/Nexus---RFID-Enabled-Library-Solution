"""Mock CCTV camera: returns a synthetic JPEG snapshot labelled with the gate, time and item."""

from datetime import UTC, datetime
from io import BytesIO

from PIL import Image, ImageDraw


class MockCamera:
    def snapshot(self, camera_code: str, context: dict) -> bytes:
        img = Image.new("RGB", (640, 360), (32, 38, 46))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 639, 359), outline=(200, 40, 40), width=6)
        lines = [
            f"{camera_code}  (simulated CCTV)",
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            f"Gate: {context.get('gate', '-')}",
            f"Accession: {context.get('accession_no') or 'unknown tag'}",
            f"EPC: {context.get('epc', '-')}",
        ]
        for i, line in enumerate(lines):
            draw.text((24, 24 + 34 * i), line, fill=(235, 235, 235))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
