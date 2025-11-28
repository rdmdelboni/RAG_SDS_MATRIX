"""
Translation support for multi-language SDS processing.

Supports automatic language detection and translation to English for extraction,
while preserving original text.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ..utils.logger import get_logger
from ..utils.cache import SimpleCache

logger = get_logger(__name__)


class Language(Enum):
    """Supported languages."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    DUTCH = "nl"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    UNKNOWN = "unknown"


@dataclass
class TranslationResult:
    """Result of text translation."""
    original_text: str
    translated_text: str
    source_language: Language
    target_language: Language
    confidence: float
    used_cache: bool = False


class LanguageDetector:
    """Detect language of text."""
    
    # Common SDS keywords by language
    LANGUAGE_KEYWORDS = {
        Language.ENGLISH: {
            "safety data sheet", "product name", "hazard", "manufacturer",
            "cas number", "emergency", "precautionary", "identification"
        },
        Language.SPANISH: {
            "hoja de datos de seguridad", "nombre del producto", "peligro",
            "fabricante", "numero cas", "emergencia", "precaucion", "identificacion"
        },
        Language.FRENCH: {
            "fiche de donnees de securite", "nom du produit", "danger",
            "fabricant", "numero cas", "urgence", "precaution", "identification"
        },
        Language.GERMAN: {
            "sicherheitsdatenblatt", "produktname", "gefahr", "hersteller",
            "cas-nummer", "notfall", "vorsichtsmassnahme", "identifizierung"
        },
        Language.PORTUGUESE: {
            "ficha de dados de seguranca", "nome do produto", "perigo",
            "fabricante", "numero cas", "emergencia", "precaucao", "identificacao"
        },
        Language.ITALIAN: {
            "scheda di sicurezza", "nome del prodotto", "pericolo",
            "produttore", "numero cas", "emergenza", "precauzione", "identificazione"
        },
    }
    
    def detect(self, text: str, use_library: bool = True) -> Tuple[Language, float]:
        """
        Detect language of text.
        
        Args:
            text: Text to analyze
            use_library: Whether to use langdetect library (if available)
        
        Returns:
            Tuple of (detected_language, confidence)
        """
        if not text or len(text.strip()) < 10:
            return Language.UNKNOWN, 0.0
        
        text_lower = text.lower()
        
        # Try library-based detection first
        if use_library:
            try:
                from langdetect import detect_langs
                results = detect_langs(text)
                if results:
                    lang_code = results[0].lang
                    confidence = results[0].prob
                    
                    # Map to our Language enum
                    lang_map = {
                        "en": Language.ENGLISH,
                        "es": Language.SPANISH,
                        "fr": Language.FRENCH,
                        "de": Language.GERMAN,
                        "pt": Language.PORTUGUESE,
                        "it": Language.ITALIAN,
                        "nl": Language.DUTCH,
                        "zh-cn": Language.CHINESE,
                        "zh-tw": Language.CHINESE,
                        "ja": Language.JAPANESE,
                        "ko": Language.KOREAN,
                    }
                    
                    detected_lang = lang_map.get(lang_code, Language.UNKNOWN)
                    return detected_lang, confidence
            except ImportError:
                logger.debug("langdetect not available, using keyword-based detection")
            except Exception as e:
                logger.warning(f"Language detection error: {e}")
        
        # Fallback: keyword-based detection
        return self._keyword_based_detection(text_lower)
    
    def _keyword_based_detection(self, text_lower: str) -> Tuple[Language, float]:
        """Detect language based on keyword matching."""
        scores = {}
        
        for lang, keywords in self.LANGUAGE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[lang] = score
        
        if not scores:
            return Language.UNKNOWN, 0.0
        
        # Get language with highest score
        best_lang = max(scores, key=scores.get)
        max_score = scores[best_lang]
        total_keywords = len(self.LANGUAGE_KEYWORDS[best_lang])
        
        confidence = min(1.0, max_score / (total_keywords * 0.3))
        
        return best_lang, confidence


class Translator:
    """Translate text between languages."""
    
    def __init__(self, cache_ttl: int = 3600):
        """Initialize translator with caching."""
        self.cache = SimpleCache(ttl_seconds=cache_ttl, max_size=1000)
        self.detector = LanguageDetector()
        logger.info("Translator initialized with caching")
    
    def translate(
        self,
        text: str,
        target_language: Language = Language.ENGLISH,
        source_language: Optional[Language] = None,
        use_library: bool = True,
    ) -> TranslationResult:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language (default: English)
            source_language: Source language (auto-detect if None)
            use_library: Whether to use translation library
        
        Returns:
            TranslationResult with original and translated text
        """
        if not text or len(text.strip()) < 3:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=Language.UNKNOWN,
                target_language=target_language,
                confidence=0.0,
            )
        
        # Detect source language if not provided
        if source_language is None:
            source_language, detect_confidence = self.detector.detect(text, use_library)
        else:
            detect_confidence = 1.0
        
        # No translation needed if already in target language
        if source_language == target_language:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                confidence=1.0,
            )
        
        # Check cache
        cache_key = f"{source_language.value}:{target_language.value}:{hash(text)}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Translation cache hit for {source_language} -> {target_language}")
            return TranslationResult(
                original_text=text,
                translated_text=cached,
                source_language=source_language,
                target_language=target_language,
                confidence=detect_confidence,
                used_cache=True,
            )
        
        # Perform translation
        if use_library:
            translated = self._translate_with_library(text, source_language, target_language)
        else:
            translated = self._translate_fallback(text, source_language, target_language)
        
        # Cache result
        self.cache.set(cache_key, translated)
        
        return TranslationResult(
            original_text=text,
            translated_text=translated,
            source_language=source_language,
            target_language=target_language,
            confidence=detect_confidence,
        )
    
    def _translate_with_library(
        self,
        text: str,
        source_language: Language,
        target_language: Language,
    ) -> str:
        """Translate using external library."""
        try:
            # Try deep-translator (free, no API key needed)
            from deep_translator import GoogleTranslator
            
            translator = GoogleTranslator(
                source=source_language.value,
                target=target_language.value
            )
            
            # Split long text into chunks (Google Translate has 5000 char limit)
            max_length = 4500
            if len(text) <= max_length:
                return translator.translate(text)
            
            # Translate in chunks
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            translated_chunks = [translator.translate(chunk) for chunk in chunks]
            return " ".join(translated_chunks)
            
        except ImportError:
            logger.warning("deep-translator not available, using fallback")
            return self._translate_fallback(text, source_language, target_language)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original on error
    
    def _translate_fallback(
        self,
        text: str,
        source_language: Language,
        target_language: Language,
    ) -> str:
        """Simple keyword-based translation for common SDS terms."""
        # Translation dictionaries for common SDS terms
        translations = {
            (Language.SPANISH, Language.ENGLISH): {
                "hoja de datos de seguridad": "safety data sheet",
                "nombre del producto": "product name",
                "peligro": "hazard",
                "fabricante": "manufacturer",
                "número cas": "cas number",
                "emergencia": "emergency",
                "precaución": "precaution",
                "identificación": "identification",
                "propiedades físicas": "physical properties",
                "estabilidad": "stability",
                "información toxicológica": "toxicological information",
            },
            (Language.FRENCH, Language.ENGLISH): {
                "fiche de données de sécurité": "safety data sheet",
                "nom du produit": "product name",
                "danger": "hazard",
                "fabricant": "manufacturer",
                "numéro cas": "cas number",
                "urgence": "emergency",
                "précaution": "precaution",
                "identification": "identification",
                "propriétés physiques": "physical properties",
                "stabilité": "stability",
                "informations toxicologiques": "toxicological information",
            },
            (Language.GERMAN, Language.ENGLISH): {
                "sicherheitsdatenblatt": "safety data sheet",
                "produktname": "product name",
                "gefahr": "hazard",
                "hersteller": "manufacturer",
                "cas-nummer": "cas number",
                "notfall": "emergency",
                "vorsichtsmaßnahme": "precaution",
                "identifizierung": "identification",
                "physikalische eigenschaften": "physical properties",
                "stabilität": "stability",
                "toxikologische informationen": "toxicological information",
            },
            (Language.PORTUGUESE, Language.ENGLISH): {
                "ficha de dados de segurança": "safety data sheet",
                "nome do produto": "product name",
                "perigo": "hazard",
                "fabricante": "manufacturer",
                "número cas": "cas number",
                "emergência": "emergency",
                "precaução": "precaution",
                "identificação": "identification",
                "propriedades físicas": "physical properties",
                "estabilidade": "stability",
                "informação toxicológica": "toxicological information",
            },
        }
        
        trans_dict = translations.get((source_language, target_language), {})
        
        if not trans_dict:
            logger.warning(f"No fallback translation for {source_language} -> {target_language}")
            return text
        
        # Replace keywords
        result = text
        for source_term, target_term in trans_dict.items():
            result = result.replace(source_term, target_term)
            result = result.replace(source_term.title(), target_term.title())
            result = result.replace(source_term.upper(), target_term.upper())
        
        return result
    
    def get_cache_stats(self) -> Dict:
        """Get translation cache statistics."""
        return self.cache.get_stats()
    
    def clear_cache(self):
        """Clear translation cache."""
        self.cache.clear()


class MultilingualExtractor:
    """Extract SDS fields from multi-language documents."""
    
    def __init__(self, translator: Optional[Translator] = None):
        """Initialize with optional translator."""
        self.translator = translator or Translator()
        logger.info("Multilingual extractor initialized")
    
    def preprocess_text(self, text: str) -> Tuple[str, Language, str]:
        """
        Preprocess text: detect language and translate if needed.
        
        Args:
            text: Original text
        
        Returns:
            Tuple of (translated_text, detected_language, original_text)
        """
        # Detect language
        language, confidence = self.translator.detector.detect(text)
        
        logger.info(f"Detected language: {language.value} (confidence: {confidence:.2f})")
        
        # Translate to English if needed
        if language != Language.ENGLISH and language != Language.UNKNOWN:
            result = self.translator.translate(text, Language.ENGLISH, language)
            logger.info(f"Translated {len(text)} characters from {language.value} to English")
            return result.translated_text, language, text
        
        return text, language, text
    
    def extract_with_translation(
        self,
        text: str,
        extractor_func,
        preserve_original: bool = True,
    ) -> Dict:
        """
        Extract fields with automatic translation support.
        
        Args:
            text: Document text (any language)
            extractor_func: Function to extract fields (expects English text)
            preserve_original: Whether to keep original language text
        
        Returns:
            Extraction results with translation metadata
        """
        # Preprocess (detect + translate)
        translated_text, source_language, original_text = self.preprocess_text(text)
        
        # Extract from translated text
        extractions = extractor_func(translated_text)
        
        # Add translation metadata
        if preserve_original and source_language != Language.ENGLISH:
            for field_name, field_data in extractions.items():
                if isinstance(field_data, dict):
                    field_data["translation"] = {
                        "source_language": source_language.value,
                        "was_translated": True,
                        "original_context": original_text[:500],  # First 500 chars
                    }
        
        return {
            "extractions": extractions,
            "metadata": {
                "source_language": source_language.value,
                "was_translated": source_language != Language.ENGLISH,
                "translation_confidence": 0.85,  # Would come from detector
            }
        }


def get_supported_languages() -> List[Language]:
    """Get list of supported languages."""
    return [
        Language.ENGLISH,
        Language.SPANISH,
        Language.FRENCH,
        Language.GERMAN,
        Language.PORTUGUESE,
        Language.ITALIAN,
    ]


def is_language_supported(language: str) -> bool:
    """Check if language is supported."""
    try:
        lang = Language(language.lower())
        return lang in get_supported_languages()
    except ValueError:
        return False
