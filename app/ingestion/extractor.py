import io
import zipfile
import hashlib
from typing import Tuple
from pypdf import PdfReader
from bs4 import BeautifulSoup
from app.core.logger import logger
from app.ingestion.ocr import ocr_fallback

class DocumentExtractor:
    @staticmethod
    def extract_text(content_bytes: bytes, filename: str = "") -> Tuple[str, str]:
        """
        Extracts plain text and generates a SHA-256 hash from content bytes.
        Handles PDF, ZIP (containing PDFs), and HTML/Text formats.
        Returns: (extracted_text, content_hash)
        """
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        filename_lower = filename.lower()
        extracted_text = ""

        # 1. ZIP File Handling (NSE Circulars)
        if filename_lower.endswith(".zip") or content_bytes.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                    pdf_texts = []
                    for file_info in z.infolist():
                        if file_info.filename.lower().endswith(".pdf"):
                            pdf_bytes = z.read(file_info.filename)
                            text, _ = DocumentExtractor._extract_from_pdf(pdf_bytes)
                            if text:
                                pdf_texts.append(text)
                        elif file_info.filename.lower().endswith((".txt", ".html", ".htm")):
                            raw = z.read(file_info.filename).decode('utf-8', errors='ignore')
                            pdf_texts.append(DocumentExtractor._clean_html(raw))
                    extracted_text = "\n\n".join(pdf_texts)
            except Exception as e:
                logger.error(f"Error unzipping document archive: {e}")

        # 2. Direct PDF File Handling
        elif filename_lower.endswith(".pdf") or content_bytes.startswith(b"%PDF"):
            extracted_text, _ = DocumentExtractor._extract_from_pdf(content_bytes)

        # 3. HTML or Plaintext Handling
        else:
            try:
                raw_text = content_bytes.decode('utf-8', errors='ignore')
                extracted_text = DocumentExtractor._clean_html(raw_text)
            except Exception as e:
                logger.error(f"Error decoding text document: {e}")

        return extracted_text.strip(), content_hash

    @staticmethod
    def _extract_from_pdf(pdf_bytes: bytes) -> Tuple[str, str]:
        extracted_pages = []
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    extracted_pages.append(text)
            
            full_text = "\n".join(extracted_pages)
            
            # OCR Fallback if text layer is empty
            if not full_text.strip():
                full_text = ocr_fallback.extract_text_from_images([pdf_bytes])
                
            return full_text, hashlib.sha256(pdf_bytes).hexdigest()
        except Exception as e:
            logger.error(f"Error parsing PDF payload: {e}")
            return "", hashlib.sha256(pdf_bytes).hexdigest()

    @staticmethod
    def _clean_html(html_content: str) -> str:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            return soup.get_text(separator=" ", strip=True)
        except Exception:
            return html_content

    @staticmethod
    def extract_dates(text: str) -> list:
        """
        Extracts dates from text preserving their exact literal representation.
        Does not convert, parse, or reinterpret format (e.g. 01/10/2026 remains 01/10/2026).
        """
        import re
        patterns = [
            r'\b\d{2}/\d{2}/\d{4}\b',
            r'\b\d{2}-\d{2}-\d{4}\b',
            r'\b\d{1,2}-(?:[A-Za-z]+)-\d{4}\b',
            r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b',
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b',
        ]
        combined = re.compile('|'.join(patterns), re.IGNORECASE)
        found = []
        for match in combined.finditer(text):
            val = match.group(0).strip()
            if val not in found:
                found.append(val)
        return found

    @staticmethod
    def parse_bse_notice(text: str) -> dict:
        """
        Parses structured fields from a BSE notice preserving exact values.
        """
        import re
        fields = {}

        # Notice No
        m_no = re.search(r'Notice\s*No\.?\s*([0-9]+-?\s*[0-9]+)', text, re.IGNORECASE)
        if m_no:
            fields['notice_no'] = re.sub(r'\s+', '', m_no.group(1))

        # Notice Date
        m_dt = re.search(r'(?:Notice\s*)?Date[:\s]*([0-9]{1,2}\s*\n?\s*[A-Za-z]{3,9}\s*\n?\s*[0-9]{4})', text, re.IGNORECASE)
        if m_dt:
            fields['notice_date'] = re.sub(r'\s+', ' ', m_dt.group(1)).strip()

        # Category
        m_cat = re.search(r'Category\s*\n\s*([^\n]+)', text, re.IGNORECASE)
        if m_cat:
            fields['category'] = m_cat.group(1).strip()

        # Segment
        m_seg = re.search(r'Segment\s*\n\s*([^\n]+)', text, re.IGNORECASE)
        if m_seg:
            fields['segment'] = m_seg.group(1).strip()

        # Department
        m_dept = re.search(r'Department\s*\n\s*([^\n]+)', text, re.IGNORECASE)
        if m_dept:
            fields['department'] = m_dept.group(1).strip()

        # Subject
        m_subj = re.search(r'Subject\s*\n(.*?)(?=Attachments|$)', text, re.DOTALL | re.IGNORECASE)
        if m_subj:
            fields['subject'] = ' '.join(m_subj.group(1).split())

        # Effective window
        m_eff = re.search(r'(?:conducted\s+from|w\.e\.f\.?|effective\s+from)\s+([^\n\.,]+)', text, re.IGNORECASE)
        if m_eff:
            fields['effective_window'] = m_eff.group(1).strip()

        # Exact dates
        fields['important_dates'] = DocumentExtractor.extract_dates(text)
        return fields

    @staticmethod
    def parse_nse_circular(text: str) -> dict:
        """
        Parses structured fields from an NSE circular preserving exact values.
        """
        import re
        fields = {}

        # Department
        m_dept = re.search(r'Department:\s*([^\n]+)', text, re.IGNORECASE)
        if m_dept:
            fields['department'] = m_dept.group(1).strip()

        # Download Ref No
        m_dl = re.search(r'Download Ref No:\s*([^\s]+)', text, re.IGNORECASE)
        if m_dl:
            fields['download_ref_no'] = m_dl.group(1).strip()

        # Circular Ref No
        m_circ = re.search(r'Circular Ref\.?\s*No:?\s*([^\n]+)', text, re.IGNORECASE)
        if m_circ:
            fields['circular_ref_no'] = m_circ.group(1).strip()

        # Date
        m_dt = re.search(r'Date:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4}|\d{1,2}[-/][A-Za-z0-9]+[-/]\d{4})', text, re.IGNORECASE)
        if m_dt:
            fields['date'] = m_dt.group(1).strip()

        # Subject
        m_sub = re.search(r'All\s+(?:Members|Participants[^\n]*)\s*\n+([^\n]+)', text, re.IGNORECASE)
        if m_sub:
            fields['subject'] = ' '.join(m_sub.group(1).split())

        # Cross reference
        m_cross = re.search(r'(?:circular\s+|circular\s+no\.?\s*)([A-Z0-9/_-]+\s+dated\s+[A-Za-z0-9, ]+)', text, re.IGNORECASE)
        if m_cross:
            fields['cross_reference'] = m_cross.group(1).strip()

        # Effective date / window
        m_eff = re.search(r'(?:Issue\s+Period|month\s+of|w\.e\.f\.?|effective\s+from)\s+([^\n\.,]+)', text, re.IGNORECASE)
        if m_eff:
            fields['effective_date'] = m_eff.group(1).strip()

        # Exact dates
        fields['important_dates'] = DocumentExtractor.extract_dates(text)
        return fields

extractor = DocumentExtractor()
