#!/usr/bin/env python3
"""
Test multi-language translation for SDS processing.
"""
from src.sds.translation import (
    Translator,
    LanguageDetector,
    MultilingualExtractor,
    Language,
    get_supported_languages,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def test_language_detection():
    """Test language detection."""
    print("=" * 80)
    print("LANGUAGE DETECTION TESTS")
    print("=" * 80)
    
    detector = LanguageDetector()
    
    test_texts = [
        ("Safety Data Sheet - Product Name: Sulfuric Acid", Language.ENGLISH),
        ("Hoja de Datos de Seguridad - Nombre del Producto: Acido Sulfurico", Language.SPANISH),
        ("Fiche de Donnees de Securite - Nom du Produit: Acide Sulfurique", Language.FRENCH),
        ("Sicherheitsdatenblatt - Produktname: Schwefelsaure", Language.GERMAN),
        ("Ficha de Dados de Seguranca - Nome do Produto: Acido Sulfurico", Language.PORTUGUESE),
    ]
    
    print("\n📝 Testing Language Detection:")
    print("-" * 80)
    
    for text, expected_lang in test_texts:
        detected_lang, confidence = detector.detect(text, use_library=False)
        status = "✓" if detected_lang == expected_lang else "✗"
        
        print(f"\n{status} Text: {text[:50]}...")
        print(f"  Expected: {expected_lang.value}")
        print(f"  Detected: {detected_lang.value} (confidence: {confidence:.2f})")


def test_translation():
    """Test translation functionality."""
    print("\n" + "=" * 80)
    print("TRANSLATION TESTS")
    print("=" * 80)
    
    translator = Translator()
    
    test_cases = [
        ("Hoja de datos de seguridad", Language.SPANISH, "Safety data sheet"),
        ("Fiche de donnees de securite", Language.FRENCH, "Safety data sheet"),
        ("Sicherheitsdatenblatt", Language.GERMAN, "Safety data sheet"),
        ("Numero CAS: 7664-93-9", Language.SPANISH, "CAS number: 7664-93-9"),
        ("Nombre del producto", Language.SPANISH, "Product name"),
    ]
    
    print("\n🌐 Testing Translation:")
    print("-" * 80)
    
    for original, source_lang, expected in test_cases:
        result = translator.translate(original, Language.ENGLISH, source_lang, use_library=False)
        
        # Check if expected keywords are in translation
        success = any(word.lower() in result.translated_text.lower() for word in expected.split())
        status = "✓" if success else "~"
        
        print(f"\n{status} {source_lang.value.upper()} -> EN")
        print(f"  Original:    {result.original_text}")
        print(f"  Translated:  {result.translated_text}")
        print(f"  Expected:    {expected}")
        print(f"  Cached:      {result.used_cache}")


def test_multilingual_extraction():
    """Test multilingual extraction."""
    print("\n" + "=" * 80)
    print("MULTILINGUAL EXTRACTION TEST")
    print("=" * 80)
    
    extractor = MultilingualExtractor()
    
    # Sample Spanish SDS text
    spanish_text = """
    Hoja de Datos de Seguridad
    Nombre del Producto: Acido Sulfurico
    Numero CAS: 7664-93-9
    Fabricante: Chemical Corp
    Clase de Peligro: 8 - Corrosivo
    """
    
    print("\n📄 Processing Spanish SDS Text:")
    print("-" * 80)
    print(f"Original: {spanish_text[:100]}...")
    
    # Preprocess
    translated, detected_lang, original = extractor.preprocess_text(spanish_text)
    
    print(f"\nDetected Language: {detected_lang.value}")
    print(f"Translation needed: {detected_lang != Language.ENGLISH}")
    
    if translated != original:
        print(f"\nTranslated Text: {translated[:200]}...")


def test_supported_languages():
    """Test supported languages."""
    print("\n" + "=" * 80)
    print("SUPPORTED LANGUAGES")
    print("=" * 80)
    
    supported = get_supported_languages()
    
    print(f"\n✓ {len(supported)} languages supported:")
    for lang in supported:
        print(f"  - {lang.value.upper():>2}: {lang.name.title()}")


def test_cache_performance():
    """Test translation caching."""
    print("\n" + "=" * 80)
    print("CACHE PERFORMANCE TEST")
    print("=" * 80)
    
    translator = Translator()
    
    text = "Hoja de datos de seguridad"
    
    # First translation (cache miss)
    print("\n🔄 First translation (cache miss):")
    result1 = translator.translate(text, Language.ENGLISH, Language.SPANISH, use_library=False)
    print(f"  Translated: {result1.translated_text}")
    print(f"  Used cache: {result1.used_cache}")
    
    # Second translation (cache hit)
    print("\n🔄 Second translation (cache hit):")
    result2 = translator.translate(text, Language.ENGLISH, Language.SPANISH, use_library=False)
    print(f"  Translated: {result2.translated_text}")
    print(f"  Used cache: {result2.used_cache}")
    
    # Cache stats
    stats = translator.get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"  Hits:      {stats['hits']}")
    print(f"  Misses:    {stats['misses']}")
    print(f"  Hit rate:  {stats['hit_rate']:.1%}")
    print(f"  Size:      {stats['size']}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MULTI-LANGUAGE SUPPORT TESTING")
    print("=" * 80)
    
    try:
        test_language_detection()
        test_translation()
        test_multilingual_extraction()
        test_supported_languages()
        test_cache_performance()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)
        
        print("\n💡 Notes:")
        print("  - Tests use fallback keyword-based translation")
        print("  - Install 'deep-translator' and 'langdetect' for better results")
        print("  - Run: pip install deep-translator langdetect")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
