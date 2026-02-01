"""BrandTranslator - Traduce identidad de marca a instrucciones visuales concretas."""

from ..models.brand import Brand


class BrandTranslator:
    """Traduce identidad de marca a instrucciones visuales concretas para prompts."""

    def __init__(self):
        """Inicializa el translator con mapeos de mood y values."""
        self.mood_map = {
            "cálido": ["warm tones", "golden hour lighting", "inviting atmosphere", "cozy feel"],
            "calido": ["warm tones", "golden hour lighting", "inviting atmosphere", "cozy feel"],
            "familiar": ["homey setting", "comfortable props", "lived-in feel", "domestic atmosphere"],
            "premium": ["luxury materials", "refined details", "elegant composition", "sophisticated aesthetic"],
            "moderno": ["clean lines", "minimalist", "contemporary aesthetic", "sleek design"],
            "modern": ["clean lines", "minimalist", "contemporary aesthetic", "sleek design"],
            "profesional": ["polished look", "corporate aesthetic", "clean composition", "business-like"],
            "casual": ["relaxed setting", "informal composition", "approachable feel", "everyday aesthetic"],
            "elegante": ["sophisticated", "refined", "graceful composition", "upscale aesthetic"],
            "divertido": ["playful elements", "vibrant colors", "energetic composition", "fun atmosphere"],
            "divertido": ["playful elements", "vibrant colors", "energetic composition", "fun atmosphere"],
            "apetitoso": ["appetizing presentation", "food styling", "tempting composition", "mouth-watering"],
            "fresco": ["fresh feel", "crisp aesthetic", "clean presentation", "vibrant colors"],
            "natural": ["organic elements", "earthy tones", "natural materials", "authentic feel"],
            "rústico": ["rustic materials", "weathered textures", "handcrafted feel", "vintage aesthetic"],
            "rustico": ["rustic materials", "weathered textures", "handcrafted feel", "vintage aesthetic"],
        }

        self.values_map = {
            "calidad": [
                "premium materials",
                "attention to detail",
                "refined finish",
                "high-quality presentation",
            ],
            "tradición": [
                "classic elements",
                "timeless design",
                "heritage aesthetic",
                "traditional composition",
            ],
            "innovación": [
                "modern twist",
                "contemporary edge",
                "cutting-edge style",
                "innovative presentation",
            ],
            "innovacion": [
                "modern twist",
                "contemporary edge",
                "cutting-edge style",
                "innovative presentation",
            ],
            "sostenibilidad": [
                "eco-friendly materials",
                "sustainable aesthetic",
                "natural elements",
                "environmentally conscious",
            ],
            "autenticidad": [
                "authentic feel",
                "genuine presentation",
                "real aesthetic",
                "honest composition",
            ],
            "excelencia": [
                "excellence in details",
                "premium quality",
                "superior presentation",
                "outstanding aesthetic",
            ],
        }

    def mood_to_visual(self, mood: list[str]) -> dict[str, list[str]]:
        """Convierte mood de marca a keywords visuales.

        Args:
            mood: Lista de palabras que describen el mood (ej: ["cálido", "familiar"])

        Returns:
            Dict con cada mood mapeado a sus keywords visuales
        """
        result = {}
        for m in mood:
            m_lower = m.lower().strip()
            keywords = self.mood_map.get(m_lower, [])
            if keywords:
                result[m] = keywords
            else:
                # Si no hay mapeo exacto, buscar parcial
                for key, values in self.mood_map.items():
                    if key in m_lower or m_lower in key:
                        result[m] = values
                        break
                if m not in result:
                    # Fallback genérico
                    result[m] = [f"{m} aesthetic", f"{m} feel"]
        return result

    def values_to_visual(self, values: list[str]) -> list[str]:
        """Convierte valores de marca a elementos visuales.

        Args:
            values: Lista de valores de marca (ej: ["calidad", "tradición"])

        Returns:
            Lista de keywords visuales combinados
        """
        result = []
        for v in values:
            v_lower = v.lower().strip()
            keywords = self.values_map.get(v_lower, [])
            if keywords:
                result.extend(keywords)
            else:
                # Buscar parcial
                for key, values_list in self.values_map.items():
                    if key in v_lower or v_lower in key:
                        result.extend(values_list)
                        break
                if not any(key in v_lower for key in self.values_map.keys()):
                    # Fallback genérico
                    result.append(f"{v} reflected in design")
        return result

    def build_brand_context(self, brand: Brand) -> str:
        """Construye contexto visual completo de la marca.

        Combina mood, values, colors, photography_style en un string estructurado
        para incluir en prompts.

        Args:
            brand: Objeto Brand con toda la configuración

        Returns:
            String estructurado con contexto visual de marca
        """
        parts = []

        # 1. Mood traducido a visual
        if brand.style.mood:
            mood_visual = self.mood_to_visual(brand.style.mood)
            mood_keywords = []
            for mood, keywords in mood_visual.items():
                mood_keywords.extend(keywords[:2])  # Tomar primeros 2 keywords por mood
            if mood_keywords:
                parts.append(f"Mood visual: {', '.join(set(mood_keywords))}")

        # 2. Values traducidos a visual
        if brand.identity.values:
            values_visual = self.values_to_visual(brand.identity.values)
            if values_visual:
                parts.append(f"Brand values reflected: {', '.join(set(values_visual[:4]))}")

        # 3. Colores estratégicos
        color_instructions = []
        if brand.palette.primary:
            color_instructions.append(f"primary brand color {brand.palette.primary} in secondary elements")
        if brand.palette.secondary:
            color_instructions.append(f"secondary color {brand.palette.secondary} as accents")
        if brand.palette.accent:
            color_instructions.append(f"accent color {brand.palette.accent} for highlights")
        if color_instructions:
            parts.append(f"Brand colors: {', '.join(color_instructions)}")

        # 4. Photography style
        if brand.style.photography_style:
            parts.append(f"Photography style: {brand.style.photography_style}")

        # 5. Backgrounds preferidos
        if brand.style.preferred_backgrounds:
            parts.append(f"Preferred backgrounds: {', '.join(brand.style.preferred_backgrounds[:2])}")

        # 6. Elementos a evitar
        if brand.style.avoid:
            parts.append(f"Avoid: {', '.join(brand.style.avoid)}")

        return "\n".join(parts)

    def get_mood_keywords_flat(self, mood: list[str]) -> list[str]:
        """Retorna keywords visuales de mood como lista plana.

        Útil para validación rápida en prompts.

        Args:
            mood: Lista de moods

        Returns:
            Lista plana de keywords visuales
        """
        mood_visual = self.mood_to_visual(mood)
        keywords = []
        for keywords_list in mood_visual.values():
            keywords.extend(keywords_list)
        return list(set(keywords))  # Remover duplicados
