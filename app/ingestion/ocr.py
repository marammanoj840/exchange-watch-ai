import logging
from app.core.logger import logger

class OCRFallback:
    @staticmethod
    def extract_text_from_images(image_bytes_list: list) -> str:
        """
        Attempts OCR extraction if pytesseract and Pillow/pdf2image are installed.
        Gracefully returns fallback text if native binary dependencies are missing.
        """
        try:
            import pytesseract
            from PIL import Image
            import io

            extracted_parts = []
            for img_bytes in image_bytes_list:
                img = Image.open(io.BytesIO(img_bytes))
                text = pytesseract.image_to_string(img)
                if text.strip():
                    extracted_parts.append(text)
            return "\n".join(extracted_parts)
        except Exception as e:
            logger.debug(f"OCR fallback unavailable or failed: {e}")
            return ""

ocr_fallback = OCRFallback()
