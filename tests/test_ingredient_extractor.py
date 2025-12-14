from src.sds.ingredient_extractor import IngredientExtractor, is_valid_cas


def test_is_valid_cas_check_digit():
    assert is_valid_cas("64-17-5") is True
    assert is_valid_cas("64-17-6") is False


def test_extract_ingredients_from_section_3_table_like_lines():
    extractor = IngredientExtractor()

    sections = {
        3: """
        COMPOSIÇÃO E INFORMAÇÕES SOBRE OS INGREDIENTES
        Etanol 64-17-5 60-70%
        Água 7732-18-5 30 – 40 %
        """
    }

    ings = extractor.extract(text="ignored", sections=sections)
    cas = {i.cas_number for i in ings}

    assert "64-17-5" in cas
    assert "7732-18-5" in cas

    ethanol = next(i for i in ings if i.cas_number == "64-17-5")
    assert ethanol.chemical_name is not None and "etanol" in ethanol.chemical_name.lower()
    assert ethanol.concentration_min == 60.0
    assert ethanol.concentration_max == 70.0


def test_extract_ocr_relaxed_cas_last_digit():
    extractor = IngredientExtractor()
    sections = {3: "Ethanol 64–17–S >= 99%"}

    ings = extractor.extract(text="ignored", sections=sections)
    assert len(ings) == 1
    assert ings[0].cas_number == "64-17-5"

