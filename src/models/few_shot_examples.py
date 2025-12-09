"""Few-shot learning examples for LLM prompt enhancement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExamplePair:
    """A single input-output example for few-shot learning."""

    input_text: str
    output_value: str
    explanation: str = ""

    def to_prompt_text(self) -> str:
        """Format example for inclusion in prompt."""
        text = f"Input: {self.input_text}\nOutput: {self.output_value}"
        if self.explanation:
            text += f"\n(Reason: {self.explanation})"
        return text


class FewShotExamples:
    """Manage domain-specific few-shot examples for extraction fields."""

    def __init__(self):
        """Initialize with default domain examples."""
        self.examples: dict[str, list[ExamplePair]] = {}
        self._load_default_examples()

    def _load_default_examples(self) -> None:
        """Load domain-specific examples for SDS fields."""
        # Product Name Examples
        self.examples["product_name"] = [
            ExamplePair(
                input_text="Product name: Sulfuric Acid 98% (Batch #001)",
                output_value="Sulfuric Acid",
                explanation="Remove percentage and batch codes"
            ),
            ExamplePair(
                input_text="ACME Chemical H2SO4 - Concentrated",
                output_value="Sulfuric Acid",
                explanation="Use IUPAC name, not brand/catalog numbers"
            ),
            ExamplePair(
                input_text="Ethanol solution 95%, molecular formula C2H5OH",
                output_value="Ethanol",
                explanation="Extract chemical name, ignore concentration and formula"
            ),
        ]

        # CAS Number Examples
        self.examples["cas_number"] = [
            ExamplePair(
                input_text="CAS Number: 7664-93-9",
                output_value="7664-93-9",
                explanation="Standard CAS format: ##### -##-#"
            ),
            ExamplePair(
                input_text="CAS: 64-17-5 (Ethanol); Contains: 7732-18-5 (Water)",
                output_value="64-17-5",
                explanation="Return PRIMARY component CAS (first listed)"
            ),
            ExamplePair(
                input_text="Cas number approximately 123456-78-9",
                output_value="123456-78-9",
                explanation="Extract even with 'approximately' qualifier"
            ),
        ]

        # UN Number Examples
        self.examples["un_number"] = [
            ExamplePair(
                input_text="UN Number: UN1198",
                output_value="1198",
                explanation="Extract 4 digits only"
            ),
            ExamplePair(
                input_text="Transport Class: ONU 2030 (flammable liquid)",
                output_value="2030",
                explanation="Works with ONU or UN prefix"
            ),
            ExamplePair(
                input_text="Section 14: UN/ID number is 1008",
                output_value="1008",
                explanation="Ignore section headers and descriptive text"
            ),
        ]

        # Hazard Class Examples
        self.examples["hazard_class"] = [
            ExamplePair(
                input_text="Hazard Class: 3 (Flammable liquid)",
                output_value="3",
                explanation="Single digit class"
            ),
            ExamplePair(
                input_text="Transport Hazard Classification: 2.1",
                output_value="2.1",
                explanation="Include decimal for sub-classes"
            ),
            ExamplePair(
                input_text="UN Class: 6.1 - Toxic substance",
                output_value="6.1",
                explanation="Decimal format for specific hazard type"
            ),
        ]

        # Packing Group Examples
        self.examples["packing_group"] = [
            ExamplePair(
                input_text="Packing Group: I",
                output_value="I",
                explanation="Roman numeral I (high hazard)"
            ),
            ExamplePair(
                input_text="PG: ii",
                output_value="II",
                explanation="Normalize to uppercase"
            ),
            ExamplePair(
                input_text="Groupe d'emballage: III",
                output_value="III",
                explanation="Roman numeral III (low hazard)"
            ),
        ]

        # H-Statements Examples
        self.examples["h_statements"] = [
            ExamplePair(
                input_text="Hazard Statements: H225 - Highly flammable liquid",
                output_value="H225",
                explanation="Extract H-codes only"
            ),
            ExamplePair(
                input_text="H302 + H312 + H332",
                output_value="H302, H312, H332",
                explanation="Convert + to comma separation"
            ),
            ExamplePair(
                input_text="H301 (Harmful if swallowed), H311 (Toxic if in contact with skin)",
                output_value="H301, H311",
                explanation="Remove descriptions, keep H-codes"
            ),
        ]

        # P-Statements Examples
        self.examples["p_statements"] = [
            ExamplePair(
                input_text="P-Statements: P280 - Wear protective gloves",
                output_value="P280",
                explanation="Extract P-codes only"
            ),
            ExamplePair(
                input_text="P302+P352: IF ON SKIN: Wash with soap and water",
                output_value="P302+P352",
                explanation="Keep + for combined statements"
            ),
            ExamplePair(
                input_text="P261, P271, P304+P340",
                output_value="P261, P271, P304+P340",
                explanation="Separate groups by comma, keep + within groups"
            ),
        ]

    def get_examples(self, field_name: str, count: int = 3) -> list[ExamplePair]:
        """Get examples for a specific field.

        Args:
            field_name: Name of extraction field
            count: Number of examples to return (default 3)

        Returns:
            List of example pairs (up to count)
        """
        examples = self.examples.get(field_name, [])
        return examples[:count]

    def add_custom_example(self, field_name: str, example: ExamplePair) -> None:
        """Add a custom example for a field.

        Args:
            field_name: Name of extraction field
            example: ExamplePair to add
        """
        if field_name not in self.examples:
            self.examples[field_name] = []
        self.examples[field_name].append(example)

    def format_examples_for_prompt(self, field_name: str, count: int = 3) -> str:
        """Format examples for inclusion in LLM prompt.

        Args:
            field_name: Name of extraction field
            count: Number of examples to include

        Returns:
            Formatted examples string for prompt
        """
        examples = self.get_examples(field_name, count)

        if not examples:
            return ""

        formatted = "\nFew-shot Examples:\n"
        for i, example in enumerate(examples, 1):
            formatted += f"\nExample {i}:\n{example.to_prompt_text()}"

        return formatted

    def enhance_prompt(self, field_name: str, base_prompt: str, example_count: int = 3) -> str:
        """Enhance base prompt with few-shot examples.

        Args:
            field_name: Name of extraction field
            base_prompt: Original prompt template
            example_count: Number of examples to add

        Returns:
            Enhanced prompt with examples
        """
        examples_text = self.format_examples_for_prompt(field_name, example_count)

        if not examples_text:
            return base_prompt

        # Insert examples before the "Text:" section
        if "Text:\n{text}" in base_prompt:
            return base_prompt.replace("Text:\n{text}", f"{examples_text}\n\nText:\n{{text}}")
        else:
            return base_prompt + examples_text

    def get_all_fields(self) -> list[str]:
        """Get list of all fields with examples."""
        return list(self.examples.keys())

    def __len__(self) -> int:
        """Get total number of example pairs."""
        return sum(len(examples) for examples in self.examples.values())


# Global instance
_global_few_shot_examples: FewShotExamples | None = None


def get_few_shot_examples() -> FewShotExamples:
    """Get or create global few-shot examples instance."""
    global _global_few_shot_examples
    if _global_few_shot_examples is None:
        _global_few_shot_examples = FewShotExamples()
    return _global_few_shot_examples
