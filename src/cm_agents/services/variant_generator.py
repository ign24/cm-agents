"""Variant Generator - Creates prompt variations for multiple design variants."""

import random

from ..models.generation import GenerationPrompt


class VariantStrategy:
    """Strategies for creating visual variations in prompts."""

    COMPOSITION_VARIATIONS = [
        "centered composition with negative space",
        "rule of thirds placement, product slightly off-center",
        "diagonal composition with dynamic angles",
        "symmetrical composition with balanced elements",
        "asymmetric composition with visual tension",
    ]

    LIGHTING_VARIATIONS = [
        "soft studio lighting with gentle shadows",
        "dramatic side lighting creating depth and dimension",
        "golden hour natural window light, warm and inviting",
        "backlit with rim lighting for elegant silhouette",
        "soft diffused lighting with minimal shadows",
        "dramatic contrast lighting with deep shadows",
    ]

    ANGLE_VARIATIONS = [
        "slight overhead angle showing top and front",
        "eye-level perspective for natural viewing",
        "low angle for dramatic presence",
        "three-quarter view showing depth",
        "slight tilt for dynamic energy",
    ]

    BACKGROUND_VARIATIONS = [
        "minimal clean background with subtle texture",
        "soft gradient background complementing product colors",
        "textured surface matching product aesthetic",
        "contextual background suggesting use case",
        "abstract geometric background with brand colors",
    ]

    @classmethod
    def create_variant_prompt(
        cls, base_prompt: GenerationPrompt, variant_number: int, total_variants: int
    ) -> GenerationPrompt:
        """
        Create a variant prompt with visual variations.

        Args:
            base_prompt: Base prompt to vary
            variant_number: Current variant number (1-based)
            total_variants: Total number of variants to generate

        Returns:
            Modified GenerationPrompt with variations
        """
        # Use variant_number as seed for consistency (same variant always gets same variation)
        random.seed(variant_number)

        # Select variations
        composition = random.choice(cls.COMPOSITION_VARIATIONS)
        lighting = random.choice(cls.LIGHTING_VARIATIONS)
        angle = random.choice(cls.ANGLE_VARIATIONS)
        background = random.choice(cls.BACKGROUND_VARIATIONS)

        # Build variation suffix
        variation_text = f", {composition}, {lighting}, {angle}, {background}"

        # Modify prompt
        variant_prompt = GenerationPrompt(
            prompt=base_prompt.prompt + variation_text,
            visual_description=base_prompt.visual_description,
            negative_prompt=base_prompt.negative_prompt,
            params=base_prompt.params,
        )

        return variant_prompt

    @classmethod
    def create_diverse_variants(
        cls, base_prompt: GenerationPrompt, num_variants: int
    ) -> list[tuple[GenerationPrompt, str]]:
        """
        Create diverse variants ensuring no duplicates.

        Args:
            base_prompt: Base prompt
            num_variants: Number of variants to create

        Returns:
            List of (variant_prompt, variation_type) tuples
        """
        variants = []
        used_combinations = set()

        for i in range(1, num_variants + 1):
            # Try to get unique combination
            max_attempts = 50
            for attempt in range(max_attempts):
                variant = cls.create_variant_prompt(base_prompt, i + attempt * 1000, num_variants)
                # Create signature from variation elements
                sig = (
                    variant.prompt[len(base_prompt.prompt) :]
                    if len(variant.prompt) > len(base_prompt.prompt)
                    else str(i)
                )
                if sig not in used_combinations:
                    used_combinations.add(sig)
                    variation_type = f"variant_{i}"
                    variants.append((variant, variation_type))
                    break
            else:
                # If we couldn't get unique, use the last one
                variant = cls.create_variant_prompt(base_prompt, i, num_variants)
                variation_type = f"variant_{i}"
                variants.append((variant, variation_type))

        return variants
