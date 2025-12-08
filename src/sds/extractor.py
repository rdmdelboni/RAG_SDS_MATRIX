"""PDF and document text extraction for SDS processing."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import logging
import os
import time
import collections
from pathlib import Path
from typing import Any


from ..config.constants import SDS_SECTIONS
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class _WarningCounter(logging.Handler):
    """Count specific warning messages emitted during PDF parsing."""

    def __init__(self, substring: str):
        super().__init__(level=logging.WARNING)
        self.substring = substring
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = record.msg
        if self.substring in str(msg):
            self.count += 1


class SDSExtractor:
    """Extract text and sections from SDS PDF documents."""

    # Patterns to detect SDS section headers (multiple formats)
    SECTION_PATTERNS = [
        re.compile(
            r"(?:^|\n)\s*(?:SEC[CÇ]ÃO|SEÇÃO|SECTION)\s+(\d+)\s*[:\-]?\s*([^\n]{5,120})",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"(?:^|\n)\s*(\d+)\s*[.:\-]\s+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][^\n]{5,120})",
            re.MULTILINE,
        ),
        re.compile(
            r"(?:^|\n)\s*Seção\s+(\d+)\s*[:\-]?\s*([^\n]{5,120})",
            re.IGNORECASE | re.MULTILINE,
        ),
    ]

    def extract_pdf(self, file_path: Path, progress_callback=None) -> dict[str, Any]:
        """Extract text and metadata from PDF.

        Args:
            file_path: Path to PDF file
            progress_callback: Optional callback(current, total, message) for progress updates

        Returns:
            Dictionary with 'text' and 'sections'
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber required")

        text_parts: list[str] = []
        raw_page_text: list[str] = []  # store original extraction before OCR fallback
        page_count = 0
        blank_pages = 0

        preprocess_tmp: Path | None = None
        input_path = file_path
        warning_counter = _WarningCounter("Cannot set gray non-stroke color")
        pdfminer_logger = logging.getLogger("pdfminer")
        pdfminer_logger.addHandler(warning_counter)

        try:
            settings = get_settings()
            if settings.processing.pdf_preprocess_enabled:
                preprocess_tmp = self._preprocess_pdf(file_path, settings.processing.pdf_preprocess_engine)
                if preprocess_tmp:
                    input_path = preprocess_tmp
        except Exception as exc:
            logger.debug("PDF preprocess skipped due to error: %s", exc)

        try:
            with pdfplumber.open(input_path) as pdf:
                page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    raw_page_text.append(text)
                    if not text.strip():
                        blank_pages += 1
                        # Try OCR immediately for empty page
                        logger.debug("Page %d empty, triggering page OCR", page_num)
                        ocr_text = self._ocr_page(page)
                        if ocr_text.strip():
                            text_parts.append(
                                f"\n--- Page {page_num} (OCR) ---\n{ocr_text}"
                            )
                        else:
                            text_parts.append(f"\n--- Page {page_num} ---\n")
                    else:
                        text_parts.append(f"\n--- Page {page_num} ---\n{text}")

        except Exception as e:
            logger.error("PDF extraction failed: %s", e)
            raise
        finally:
            if preprocess_tmp:
                try:
                    Path(preprocess_tmp).unlink(missing_ok=True)
                except Exception:
                    pass
            pdfminer_logger.removeHandler(warning_counter)

        full_text = "\n".join(text_parts)

        # === Global OCR Fallback Decision ===
        try:
            settings = get_settings()
            if not settings.processing.ocr_fallback_enabled:
                return {"text": full_text, "page_count": page_count, "sections": self._extract_sections(full_text)}

            total_chars = sum(len(t) for t in raw_page_text)
            avg_chars = total_chars / page_count if page_count else 0
            blank_ratio = blank_pages / page_count if page_count else 0.0
            # Configurable thresholds from settings
            min_avg_chars = settings.processing.ocr_min_avg_chars_per_page
            max_blank_ratio = settings.processing.ocr_max_blank_page_ratio

            if (avg_chars < min_avg_chars or blank_ratio > max_blank_ratio) and page_count > 0:
                logger.info(
                    "Triggering full-document OCR fallback (avg_chars=%.1f blank_ratio=%.2f)",
                    avg_chars,
                    blank_ratio,
                )
                if progress_callback:
                    progress_callback(0, page_count, f"Starting OCR on {page_count} pages...")
                try:
                    ocr_text = self._ocr_pdf_doctr(file_path, progress_callback=progress_callback)
                    if ocr_text and len(ocr_text.strip()) > len(full_text.strip()) * 0.8:
                        full_text = ocr_text
                        logger.info(
                            "Full OCR fallback used (length=%d, original=%d)",
                            len(ocr_text),
                            len("\n".join(text_parts)),
                        )
                except Exception as exc:  # pragma: no cover - best effort
                    logger.warning("Full OCR fallback failed: %s", exc)
            # Trigger OCR if pdfminer logged many graphics warnings
            warn_threshold = settings.processing.pdf_graphics_warning_threshold
            if warn_threshold > 0 and warning_counter.count >= warn_threshold:
                min_chars_for_graphics = min_avg_chars * 0.5
                if avg_chars >= min_chars_for_graphics:
                    logger.info(
                        "Skipping graphics-warning OCR: avg_chars=%.1f >= %.1f (warnings=%d, threshold=%d)",
                        avg_chars,
                        min_chars_for_graphics,
                        warning_counter.count,
                        warn_threshold,
                    )
                else:
                    logger.info(
                        "Triggering OCR fallback due to %d PDF graphics warnings (threshold=%d)",
                        warning_counter.count,
                        warn_threshold,
                    )
                    if progress_callback:
                        progress_callback(0, page_count, f"Starting OCR on {page_count} pages (graphics detected)...")
                    try:
                        ocr_text = self._ocr_pdf_doctr(file_path, progress_callback=progress_callback)
                        if ocr_text and len(ocr_text.strip()) > len(full_text.strip()) * 0.5:
                            full_text = ocr_text
                            logger.info("Full OCR fallback used after graphics warnings")
                    except Exception as exc:  # pragma: no cover
                        logger.warning("OCR fallback after graphics warnings failed: %s", exc)
        except Exception as exc:  # pragma: no cover
            logger.debug("OCR fallback decision failed: %s", exc)

        # If pdfplumber yielded nothing, try a full docTR OCR as a last resort
        if page_count == 0 or not full_text.strip():
            doctr_text = self._ocr_pdf_doctr(file_path)
            if doctr_text.strip():
                return {
                    "text": doctr_text,
                    "page_count": page_count or len(doctr_text.split("\n\n")),
                    "sections": self._extract_sections(doctr_text),
                }

        return {
            "text": full_text,
            "page_count": page_count,
            "sections": self._extract_sections(full_text),
        }

    def _preprocess_pdf(self, file_path: Path, engines: str) -> Path | None:
        """Optionally normalize PDFs (flatten patterns) before pdfplumber parses them."""
        engine_list = [e.strip() for e in engines.split(",") if e.strip()]
        for engine in engine_list:
            if engine.lower() in ("gs", "ghostscript"):
                bin_name = shutil.which("gs") or shutil.which("ghostscript")
                if not bin_name:
                    continue
                tmp = Path(tempfile.mkstemp(suffix=".pdf")[1])
                cmd = [
                    bin_name,
                    "-sDEVICE=pdfwrite",
                    "-dNOPAUSE",
                    "-dBATCH",
                    "-dSAFER",
                    "-dCompatibilityLevel=1.7",
                    "-sOutputFile=%s" % tmp,
                    str(file_path),
                ]
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    logger.info("PDF preprocessed via ghostscript: %s", tmp.name)
                    return tmp
                except Exception as exc:
                    logger.debug("Ghostscript preprocess failed: %s", exc)
                    tmp.unlink(missing_ok=True)
            if engine.lower() == "qpdf":
                bin_name = shutil.which("qpdf")
                if not bin_name:
                    continue
                tmp = Path(tempfile.mkstemp(suffix=".pdf")[1])
                cmd = [bin_name, "--stream-data=preserve", "--object-streams=preserve", str(file_path), str(tmp)]
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    logger.info("PDF preprocessed via qpdf: %s", tmp.name)
                    return tmp
                except Exception as exc:
                    logger.debug("qpdf preprocess failed: %s", exc)
                    tmp.unlink(missing_ok=True)

        return None

    def _ocr_page(self, page: Any) -> str:
        """Extract text from page using OCR (docTR primary, Ollama fallback).

        Args:
            page: pdfplumber page object

        Returns:
            Extracted text
        """
        try:
            import io

            page_img = page.to_image(resolution=150)
            pil_img = getattr(page_img, "original", None)
            if pil_img is None:
                return ""

            # Try docTR first (faster, better for structured docs)
            text = self._ocr_page_doctr(pil_img)
            if text.strip():
                logger.debug("docTR extracted %d characters", len(text))
                return text

            # Fallback to Ollama if docTR fails or returns empty
            logger.debug("docTR returned empty, trying Ollama fallback")
            from ..models import get_ollama_client

            ollama = get_ollama_client()
            img_bytes = io.BytesIO()
            pil_img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            self._throttle_ocr()
            text = ollama.ocr_image_bytes(img_bytes.read())
            logger.debug("Ollama extracted %d characters", len(text))
            return text

        except TimeoutError as e:
            logger.debug("OCR timeout (skipping): %s", e)
            return ""
        except Exception as e:
            logger.debug("OCR failed (skipping): %s", e)
            return ""

    def _ocr_page_doctr(self, pil_image: Any) -> str:
        """Extract text from PIL image using docTR.

        Args:
            pil_image: PIL Image object

        Returns:
            Extracted text
        """
        try:
            import torch
            from doctr.io import DocumentFile
            from doctr.models import ocr_predictor

            # Initialize model once (lazy load via class var to avoid repeated init)
            if not hasattr(self, '_doctr_model'):
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info("Initializing docTR model on %s (first use)", device)
                self._doctr_model = ocr_predictor(pretrained=True).to(device)

            # Predict on image
            doc = DocumentFile.from_pil(pil_image)
            result = self._doctr_model(doc)

            # Extract text from result
            text_parts = []
            for page in result.pages:
                for block in page.blocks:
                    for line in block.lines:
                        for word in line.words:
                            text_parts.append(word.value)
                        text_parts.append("\n")

            return " ".join(text_parts)

        except ImportError:
            logger.debug("docTR not available (install with: pip install doctr)")
            return ""
        except Exception as e:
            logger.debug("docTR extraction failed: %s", e)
            return ""

    def _ocr_pdf_full(self, file_path: Path) -> str:
        """Perform OCR on all pages of a PDF using docTR (fast) or Ollama (fallback)."""
        try:
            import pdfplumber
            from ..models import get_ollama_client

            parts: list[str] = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_img = page.to_image(resolution=150)
                        pil_img = getattr(page_img, "original", None)
                        if pil_img is None:
                            continue

                        # Try docTR first (faster, better for structured docs)
                        text = self._ocr_page_doctr(pil_img)
                        if text.strip():
                            parts.append(f"\n--- Page {page_num} (docTR OCR) ---\n{text}")
                            continue

                        # Fallback to Ollama
                        import io

                        ollama = get_ollama_client()
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        buf.seek(0)
                        self._throttle_ocr()
                        text = ollama.ocr_image_bytes(buf.read())
                        if text:  # Only add non-empty results
                            parts.append(f"\n--- Page {page_num} (Ollama OCR) ---\n{text}")

                    except TimeoutError:  # pragma: no cover
                        logger.debug("Full OCR page %d timeout (skipping)", page_num)
                        continue
                    except Exception as e:  # pragma: no cover
                        logger.debug("Full OCR page %d failed: %s", page_num, e)
                        continue

            return "\n".join(parts)
        except Exception as e:  # pragma: no cover
            logger.debug("Full PDF OCR failed (skipping): %s", e)
            return ""

    def _ocr_pdf_doctr(self, file_path: Path, progress_callback=None) -> str:
        """OCR an entire PDF using docTR directly (bypasses pdfplumber).
        
        Args:
            file_path: Path to PDF file
            progress_callback: Optional callback function(current, total, message)
        """
        try:
            import torch
            from doctr.io import DocumentFile
            from doctr.models import ocr_predictor

            if not hasattr(self, "_doctr_model"):
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info("Initializing docTR model on %s (full-PDF fallback)", device)
                self._doctr_model = ocr_predictor(pretrained=True).to(device)

            doc = DocumentFile.from_pdf(file_path)
            total_pages = len(doc)
            
            if progress_callback:
                progress_callback(0, total_pages, f"OCR starting ({total_pages} pages)...")
            
            result = self._doctr_model(doc)

            text_parts = []
            for page_idx, page in enumerate(result.pages, 1):
                if progress_callback:
                    progress_callback(page_idx, total_pages, f"OCR page {page_idx}/{total_pages}...")
                
                for block in page.blocks:
                    for line in block.lines:
                        line_text = " ".join(word.value for word in line.words)
                        text_parts.append(line_text)
                text_parts.append("\n")

            return "\n".join(text_parts)
        except ImportError:
            logger.debug("docTR not available for full-PDF OCR")
            return ""
        except Exception as e:  # pragma: no cover
            logger.debug("docTR full-PDF OCR failed: %s", e)
            return ""

    # === OCR Rate Limiting ===
    _ocr_times: collections.deque[float] = collections.deque()

    def _throttle_ocr(self) -> None:
        """Throttle OCR requests to avoid overloading OCR backend."""
        try:
            max_rps = int(os.getenv("OCR_RPS", "30"))
        except Exception:
            max_rps = 30
        now = time.time()
        self._ocr_times.append(now)
        one_sec_ago = now - 1.0
        while self._ocr_times and self._ocr_times[0] < one_sec_ago:
            self._ocr_times.popleft()
        if len(self._ocr_times) >= max_rps:
            # Sleep to respect rate per second
            sleep_for = max(0.005, self._ocr_times[0] + 1.0 - now)
            time.sleep(sleep_for)

    def _extract_sections(self, text: str) -> dict[int, str]:
        """Extract SDS sections from text with improved detection.

        Args:
            text: Full document text

        Returns:
            Dictionary mapping section numbers to section text
        """
        sections = {}
        section_positions = []

        # Try all patterns to find section headers
        for pattern in self.SECTION_PATTERNS:
            matches = pattern.finditer(text)
            for match in matches:
                try:
                    section_num = int(match.group(1))
                    if 1 <= section_num <= 16:
                        section_positions.append(
                            (section_num, match.start(), match.end())
                        )
                except (ValueError, IndexError):
                    continue

        # Sort by position and extract section text
        if section_positions:
            section_positions.sort(key=lambda x: x[1])

            for idx, (section_num, start, end) in enumerate(section_positions):
                # Find end boundary (next section or end of text)
                next_start = (
                    section_positions[idx + 1][1]
                    if idx + 1 < len(section_positions)
                    else len(text)
                )

                # Extract section content (skip header line)
                section_text = text[end:next_start].strip()

                # Only store if not duplicate and has content
                if section_num not in sections and len(section_text) > 20:
                    sections[section_num] = section_text

        # Fallback: try to split by likely section content
        if len(sections) < 5:  # Too few sections found
            logger.debug("Few sections detected, using fallback heuristics")
            sections = self._extract_sections_fallback(text)

        logger.info("Extracted %d SDS sections", len(sections))
        return sections

    def _extract_sections_fallback(self, text: str) -> dict[int, str]:
        """Fallback section extraction using content heuristics.

        Args:
            text: Full document text

        Returns:
            Dictionary mapping section numbers to text
        """
        # Map keywords to likely section numbers
        section_keywords = {
            1: ["identification", "identificação", "produto"],
            2: ["hazard", "perigo", "classificação"],
            3: ["composition", "composição", "ingredientes"],
            4: ["first aid", "primeiros", "socorros"],
            5: ["fire fighting", "combate", "incêndio"],
            10: ["stability", "estabilidade", "reatividade"],
            14: ["transport", "transporte"],
        }

        sections = {}
        lines = text.split("\n")
        current_section = None
        current_text = []

        for line in lines:
            line_lower = line.lower()

            # Check if line indicates a section start
            detected_section = None
            for sec_num, keywords in section_keywords.items():
                if any(kw in line_lower for kw in keywords):
                    detected_section = sec_num
                    break

            if detected_section:
                # Save previous section
                if current_section and current_text:
                    sections[current_section] = "\n".join(current_text).strip()

                # Start new section
                current_section = detected_section
                current_text = [line]
            elif current_section:
                current_text.append(line)

        # Save last section
        if current_section and current_text:
            sections[current_section] = "\n".join(current_text).strip()

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

    def extract_document(self, file_path: Path, progress_callback=None) -> dict[str, Any]:
        """Extract all information from an SDS document.

        Args:
            file_path: Path to document
            progress_callback: Optional callback(current, total, message) for progress updates

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
                result = self.extract_pdf(file_path, progress_callback=progress_callback)
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
