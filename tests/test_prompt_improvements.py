"""Tests for improved prompts with Chain of Thought."""

from src.config.constants import EXTRACTION_FIELDS


class TestPromptImprovements:
    """Test suite for Chain of Thought prompt improvements."""

    def test_product_name_prompt_has_cot(self):
        """Test that product_name prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "product_name")

        # Should have step-by-step instructions
        assert "Step 1:" in field.prompt_template
        assert "Step 2:" in field.prompt_template
        assert "Step 3:" in field.prompt_template
        assert "Step 4:" in field.prompt_template
        assert "Step 5:" in field.prompt_template

    def test_cas_number_prompt_has_cot(self):
        """Test that cas_number prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "cas_number")

        assert "Step 1:" in field.prompt_template
        assert "Format validation:" in field.prompt_template
        assert "CORRECT:" in field.prompt_template
        assert "INCORRECT:" in field.prompt_template

    def test_un_number_prompt_has_cot(self):
        """Test that un_number prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "un_number")

        assert "Step 1:" in field.prompt_template
        assert "Step 2:" in field.prompt_template
        assert "Valid examples:" in field.prompt_template
        assert "Invalid examples:" in field.prompt_template

    def test_hazard_class_prompt_has_cot(self):
        """Test that hazard_class prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "hazard_class")

        assert "Step 1:" in field.prompt_template
        assert "Step 2:" in field.prompt_template
        assert "Class meanings:" in field.prompt_template
        assert "Valid examples:" in field.prompt_template
        assert "Invalid examples:" in field.prompt_template

    def test_packing_group_prompt_has_cot(self):
        """Test that packing_group prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "packing_group")

        assert "Step 1:" in field.prompt_template
        assert "Step 2:" in field.prompt_template
        assert "Valid examples:" in field.prompt_template
        assert "Invalid examples:" in field.prompt_template

    def test_h_statements_prompt_has_cot(self):
        """Test that h_statements prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "h_statements")

        assert "Step 1:" in field.prompt_template
        assert "Step 2:" in field.prompt_template
        assert "Valid H-statements range:" in field.prompt_template

    def test_p_statements_prompt_has_cot(self):
        """Test that p_statements prompt includes chain of thought steps."""
        field = next(f for f in EXTRACTION_FIELDS if f.name == "p_statements")

        assert "Step 1:" in field.prompt_template
        assert "Step 2:" in field.prompt_template
        assert "Valid P-statement ranges:" in field.prompt_template

    def test_prompts_have_examples(self):
        """Test that all critical prompts have examples."""
        critical_fields = ["product_name", "cas_number", "un_number", "hazard_class", "packing_group"]

        for field_name in critical_fields:
            field = next(f for f in EXTRACTION_FIELDS if f.name == field_name)
            assert "Example" in field.prompt_template or "example" in field.prompt_template, \
                f"{field_name} prompt missing examples"

    def test_prompts_have_input_output_format(self):
        """Test that prompts clarify input/output format."""
        critical_fields = ["product_name", "cas_number", "un_number"]

        for field_name in critical_fields:
            field = next(f for f in EXTRACTION_FIELDS if f.name == field_name)
            # Should have examples showing input/output or validation examples
            assert ("Input:" in field.prompt_template or "Output:" in field.prompt_template or
                    "→" in field.prompt_template or "example" in field.prompt_template.lower()), \
                f"{field_name} prompt missing input/output format clarification"

    def test_prompts_longer_than_original(self):
        """Test that improved prompts are longer (with more guidance)."""
        # These should be significantly longer than simple prompts
        field = next(f for f in EXTRACTION_FIELDS if f.name == "cas_number")

        # CoT prompts should be substantially longer
        assert len(field.prompt_template) > 600, \
            "CAS number prompt should be longer with CoT instructions"

    def test_all_extraction_fields_have_prompts(self):
        """Test that all required extraction fields have non-empty prompts."""
        for field in EXTRACTION_FIELDS:
            if field.required:  # Check required fields
                assert field.prompt_template, f"Required field {field.name} missing prompt"
                assert len(field.prompt_template) > 50, \
                    f"Required field {field.name} has insufficient prompt"
