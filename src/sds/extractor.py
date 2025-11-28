"""PDF and document text extraction for SDS processing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


from ..config.constants import SDS_SECTIONS
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SDSExtractor:
    """Extract text and sections from SDS PDF documents."""

    # Pattern to detect SDS section headers
    SECTION_PATTERN = re.compile(
        r"(?:SECÇÃO|SEÇÃO|SECTION|Seção)\s+(\d+)[:\s\-]+(.+?)(?=(?:SECÇÃO|SEÇÃO|SECTION|Seção)\s+\d+|$)",
        re.IGNORECASE | re.DOTALL,
    )

    def extract_pdf(self, file_path: Path) -> dict[str, Any]:
        """Extract text and metadata from PDF.

        Args:
            file_path: Path to PDF file

        Returns:
            Dictionary with 'text' and 'sections'
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber required")

        text_parts = []
        page_count = 0

        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    # Try to extract text
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"\n--- Page {page_num} ---\n{text}")
                    else:
                        # Fallback to OCR if no text extracted
                        logger.warning(
                            "Page %d has no text, attempting OCR",
                            page_num,
                        )
                        text = self._ocr_page(page)
                        if text:
                            text_parts.append(
                                f"\n--- Page {page_num} (OCR) ---\n{text}"
                            )

        except Exception as e:
            logger.error("PDF extraction failed: %s", e)
            raise

        full_text = "\n".join(text_parts)

        return {
            "text": full_text,
            "page_count": page_count,
            "sections": self._extract_sections(full_text),
        }

    def _ocr_page(self, page: Any) -> str:
        """Extract text from page using OCR.

        Args:
            page: pdfplumber page object

        Returns:
            Extracted text
        """
        try:
            # Convert page to image
            import io

            from ..models import get_ollama_client

            img = page.to_image()
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            # Use Ollama OCR
            ollama = get_ollama_client()
            text = ollama.ocr_image_bytes(img_bytes.read())

            logger.debug("OCR extracted %d characters", len(text))
            return text

        except Exception as e:
            logger.warning("OCR failed: %s", e)
            return ""

    def _extract_sections(self, text: str) -> dict[int, str]:
        """Extract SDS sections from text.

        Args:
            text: Full document text

        Returns:
            Dictionary mapping section numbers to section text
        """
        sections = {}

        # Try to find explicit section markers
        matches = list(self.SECTION_PATTERN.finditer(text))

        if matches:
            # Explicit sections found
            for idx, match in enumerate(matches):
                try:
                    section_num = int(match.group(1))
                    start = match.start()
                    end = (
                        matches[idx + 1].start()
                        if idx + 1 < len(matches)
                        else len(text)
                    )
                    sections[section_num] = text[start:end].strip()
                except (ValueError, IndexError):
                    continue
        else:
            # Fallback: try to split by likely section content
            # This is a simple heuristic for documents without explicit headers
            lines = text.split("\n")
            current_section = None

            for line in lines:
                # Look for patterns that indicate section start
                if any(
                    keyword in line.lower()
                    for keyword in [
                        "identification",
                        "hazard",
                        "composition",
                        "first aid",
                        "fire fighting",
                        "accidental release",
                        "handling and storage",
                        "exposure control",
                        "physical and chemical",
                        "stability and reactivity",
                        "toxicological",
                        "ecological",
                        "disposal",
                        "transport information",
                        "regulatory information",
                    ]
                ):
                    current_section = line
                    sections[len(sections) + 1] = line + "\n"
                elif current_section and len(sections) > 0:
                    sections[max(sections.keys())] += line + "\n"

        logger.info("Extracted %d SDS sections", len(sections))
        return sections

    def get_section_text(
        self,
        text: str,
        sections: dict[int, str],
        section_num: int,
    ) -> str:
        """Get text for a specific section.

        Args:
            text: Full document text
            sections: Extracted sections mapping
            section_num: Section number (1-16)

        Returns:
            Section text or empty string
        """
        if section_num in sections:
            return sections[section_num]

        # Fallback: search for section name
        section_name = SDS_SECTIONS.get(section_num, "")
        if section_name:
            # Try to find section by name
            pattern = re.compile(
                f"(?:SECÇÃO|SEÇÃO|{re.escape(section_name)}).*?(?=SECÇÃO|SEÇÃO|$)",
                re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(text)
            if match:
                return match.group(0)

        return ""

    def extract_document(self, file_path: Path) -> dict[str, Any]:
        """Extract all information from an SDS document.

        Args:
            file_path: Path to document

        Returns:
            Dictionary with extracted data
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("Extracting document: %s", file_path.name)

        try:
            # Extract based on file type
            if file_path.suffix.lower() == ".pdf":
                result = self.extract_pdf(file_path)
            else:
                # Treat as text file
                text = file_path.read_text(encoding="utf-8")
                result = {
                    "text": text,
                    "page_count": None,
                    "sections": self._extract_sections(text),
                }

            return result

        except Exception as e:
            logger.error("Document extraction failed: %s", e)
            raise
