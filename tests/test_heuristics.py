from src.sds.heuristics import HeuristicExtractor


def test_heuristic_extracts_core_fields():
    extractor = HeuristicExtractor()

    section_text = """
    Número ONU: UN 1824
    Classe de risco: 8
    Grupo de embalagem: II
    """
    full_text = """
    Nome do produto: Hidróxido de Sódio
    CAS: 1310-73-2
    """ + section_text

    sections = {14: section_text}

    results = extractor.extract_all_fields(full_text, sections)

    assert results["cas_number"]["value"] == "1310-73-2"
    assert results["un_number"]["value"] == "1824"
    assert results["hazard_class"]["value"] == "8"
    assert results["packing_group"]["value"] == "II"
