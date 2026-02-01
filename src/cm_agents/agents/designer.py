"""Agente Diseñador - Construye prompts optimizados con best practices de diseño 2026.

.. deprecated:: 2.2.0
    Este agente está deprecado. Usar CreativeEngine en su lugar,
    que fusiona Extractor + Designer en un solo agente optimizado.
"""

import json
import warnings
from pathlib import Path

import anthropic
from rich.console import Console

from ..models.brand import Brand
from ..models.generation import GenerationParams, GenerationPrompt, ReferenceAnalysis
from ..models.product import Product
from .base import BaseAgent
from .brand_translator import BrandTranslator

console = Console()

# Tipo para estilos (dinámico, se valida en runtime)
DesignStyle = str  # Los estilos válidos se cargan del knowledge base


def get_available_styles() -> list[str]:
    """Carga los estilos disponibles desde el knowledge base."""
    knowledge_path = Path(__file__).parent.parent.parent.parent / "knowledge" / "design_2026.json"
    if knowledge_path.exists():
        with open(knowledge_path, encoding="utf-8") as f:
            data = json.load(f)
            return list(data.get("styles", {}).keys())
    # Fallback básico si no existe el archivo
    return ["minimal_clean", "lifestyle_warm", "editorial_magazine"]


# Constante para compatibilidad con CLI (se actualiza al importar)
DESIGN_STYLES: list[str] = get_available_styles()

DESIGNER_SYSTEM_PROMPT = """Sos un diseñador gráfico experto y director creativo especializado en contenido para redes sociales, con 15+ años de experiencia en branding visual y fotografía de productos.

## Tu Expertise

### Principios de Diseño que Dominás:
- **Composición**: Rule of thirds, golden ratio, negative space, leading lines, framing
- **Jerarquía Visual**: Focal point claro, elementos secundarios que soportan sin competir
- **Psicología del Color**: Colores que generan engagement en Instagram (coral, sage green, golden yellow, terracotta)
- **Iluminación**: Soft studio, golden hour, natural window, dramatic contrast, backlit
- **Tipografía integrada**: Texto como parte del diseño, no superpuesto

### Tendencias 2026 que Aplicás:
1. **Autenticidad sobre perfección**: El contenido que se siente "real" y táctil supera al contenido pulido artificialmente
2. **Biophilic Design**: Integración de elementos naturales y materiales orgánicos
3. **Tactile Craft**: Énfasis en texturas y calidad artesanal
4. **Warm Tones**: Paletas de colores cálidas y terrosas
5. **Imperfect Aesthetics**: Evitar el look "demasiado perfecto" de AI
6. **Texto integrado**: Tipografía que forma parte orgánica del diseño visual

## Composición Profesional (CRÍTICO):

SIEMPRE especificar técnica de composición específica:
- **Rule of thirds**: Colocar producto en intersecciones de líneas (no centrado)
- **Golden ratio**: Usar proporción 1:1.618 para elementos principales
- **Centered**: Solo cuando el estilo lo requiere (minimal, simétrico)
- **Negative space estratégico**: Dejar áreas vacías intencionalmente para texto (top, bottom, o sides según tamaño)
- **Visual hierarchy**: Producto siempre como focal point primario, props secundarios
- **Adaptar al tamaño**: Feed (4:5) tiene safe zones diferentes a Story (9:16)

## Integración de Identidad de Marca (CRÍTICO):

- **Traducir mood de marca a keywords visuales específicos**: Si la marca es "cálido y familiar", usar "warm tones, golden hour lighting, inviting atmosphere, cozy feel"
- **Usar colores de marca estratégicamente**: Colores primarios en elementos secundarios (props, fondo, acentos), NO dominar la composición
- **Reflejar valores de marca**: Si la marca valora "calidad", incluir "premium materials, attention to detail, refined finish"
- **Mantener coherencia**: Seguir photography_style de la marca y evitar elementos en brand.style.avoid
- **Mood visual**: El mood de marca debe traducirse a atmósfera visual concreta, no solo mencionarse

### Best Practices para Prompts de Imagen AI:
- **Estructura OBLIGATORIA**: COMPOSITION + LIGHTING + COLOR + MOOD + PRODUCT + TEXT + QUALITY
  - COMPOSITION: Técnica específica (rule of thirds, golden ratio, centered) + negative space + visual hierarchy
  - LIGHTING: Estilo específico (soft studio, golden hour, natural window, etc.)
  - COLOR: Paleta de marca integrada estratégicamente + colores de referencia
  - MOOD: Keywords visuales traducidos de mood y valores de marca
  - PRODUCT: Descripción mínima (la imagen es referencia visual)
  - TEXT: Instrucciones específicas de tipografía integrada
  - QUALITY: Tags de calidad profesional
- Ser específico en detalles de textura, color exacto, forma y proporciones
- Incluir siempre: lighting style, mood, composition technique específica
- **IMPORTANTE**: El texto (precio, nombre del producto) debe ser parte de la imagen generada, NO overlay posterior
- Quality tags: "professional product photography", "8K detail", "sharp focus", "commercial quality"

### Especificaciones Instagram 2026:
- Feed (4:5, 1080x1350): Safe zones 150px top, 200px bottom
- Story (9:16, 1080x1920): Safe zones 250px top, 340px bottom
- Evitar colores que se mezclen con el UI de Instagram

## Tu Tarea

Dado:
1. Análisis de una imagen de referencia (estilo visual extraído de Pinterest) - COPIAR el estilo tipográfico si tiene texto
2. Configuración de la marca (colores, mood, valores, estilo)
3. Información del producto (nombre, precio, descripción visual)
4. Estilo deseado (minimal, lifestyle, editorial, authentic, biophilic)
5. Tamaño objetivo (feed o story)

Generá un prompt PROFESIONAL que:
- **Aplique composición profesional específica** (rule of thirds, golden ratio, o centered según análisis)
- **Incluya negative space estratégico** para texto según tamaño (feed vs story)
- **Traduzca mood y valores de marca** a keywords visuales concretos (no solo menciones)
- **Integre colores de marca** en elementos secundarios de forma sutil
- **Mantenga visual hierarchy** clara (producto = focal point)
- **Siga las tendencias 2026** de autenticidad y craft
- **INCLUYA el texto como parte del diseño** (nombre del producto, precio) con tipografía que coincida con el estilo de la referencia
- **Evite artefactos comunes de AI** (demasiado perfecto, artificial, plástico)

## IMPORTANTE - Texto Integrado:
El prompt DEBE incluir instrucciones para generar texto dentro de la imagen:
- Nombre del producto: usar tipografía elegante que coincida con el estilo de la referencia
- Precio: incluirlo como badge o elemento gráfico integrado
- Copiar el estilo tipográfico de la referencia de Pinterest (si tiene texto)
- El texto debe verse como parte natural del diseño, NO como overlay

## Formato de Respuesta (JSON estricto):
{
  "prompt": "El prompt completo y optimizado en inglés, INCLUYENDO instrucciones de texto integrado",
  "visual_description": "Descripción visual detallada del producto específico",
  "negative_prompt": "Elementos a evitar, específicos para el estilo elegido",
  "design_rationale": "Breve explicación de las decisiones de diseño tomadas",
  "params": {
    "aspect_ratio": "4:5 o 9:16",
    "quality": "high",
    "size": "1080x1350 o 1080x1920"
  }
}

## Notas Críticas:
- El prompt DEBE estar en inglés (mejor rendimiento con modelos de imagen)
- Priorizá autenticidad sobre perfección técnica
- El producto Y EL TEXTO son generados por AI como parte del mismo diseño
- Copiar el estilo tipográfico de la referencia si tiene texto visible
- SIEMPRE especificar técnica de composición específica (no genérica)
- SIEMPRE traducir mood de marca a keywords visuales concretos

## MUY IMPORTANTE - IMAGEN DEL PRODUCTO COMO REFERENCIA:
La imagen real del producto se pasa DIRECTAMENTE al generador como referencia visual.
- NO necesitás describir el producto en detalle - el generador VE la imagen
- Enfocate en el ESTILO, COMPOSICIÓN, ILUMINACIÓN y TEXTO
- El generador copiará el producto de la imagen de referencia automáticamente
- Solo pedí que mantenga el producto fiel a la referencia visual
"""


class DesignerAgent(BaseAgent):
    """Agente diseñador que construye prompts con conocimiento de diseño 2026.

    .. deprecated:: 2.2.0
        Usar CreativeEngine en su lugar.
    """

    def __init__(self):
        warnings.warn(
            "DesignerAgent is deprecated. Use CreativeEngine instead, "
            "which combines Extractor + Designer in a single optimized agent.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__()
        self.client = anthropic.Anthropic(api_key=self._get_env("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.knowledge_base = self._load_knowledge_base()
        self.brand_translator = BrandTranslator()

    def _validate_env(self) -> None:
        """Valida que ANTHROPIC_API_KEY esté configurada."""
        if not self._get_env("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY no configurada")

    def _load_knowledge_base(self) -> dict:
        """Carga la base de conocimiento de diseño."""
        knowledge_path = (
            Path(__file__).parent.parent.parent.parent / "knowledge" / "design_2026.json"
        )
        if knowledge_path.exists():
            with open(knowledge_path, encoding="utf-8") as f:
                return json.load(f)
        console.print("[yellow][!] Knowledge base no encontrada, usando defaults[/yellow]")
        return {}

    @property
    def name(self) -> str:
        return "Designer"

    @property
    def description(self) -> str:
        return "Diseñador experto que construye prompts con best practices 2026"

    def _get_style_config(self, style: str) -> dict:
        """Obtiene la configuración de un estilo desde el knowledge base."""
        styles = self.knowledge_base.get("styles", {})
        return styles.get(style, styles.get("minimal_clean", {}))

    def _get_category_guidelines(self, category: str) -> dict:
        """Obtiene las guías específicas para una categoría de producto."""
        categories = self.knowledge_base.get("category_guidelines", {})
        return categories.get(category, {})

    def _get_lighting_prompt(self, lighting_key: str) -> str:
        """Obtiene el prompt de iluminación desde el knowledge base."""
        lighting_styles = self.knowledge_base.get("lighting_styles", {})
        lighting = lighting_styles.get(lighting_key, {})
        return lighting.get("prompt", "soft natural lighting")

    def _get_negative_prompts(self, style: str) -> list[str]:
        """Obtiene los negative prompts para un estilo."""
        neg_prompts = self.knowledge_base.get("negative_prompts", {})
        universal = neg_prompts.get("universal", [])
        ai_artifacts = neg_prompts.get("ai_artifacts", [])
        style_specific = neg_prompts.get("style_specific", {}).get(
            style.replace("_clean", "")
            .replace("_warm", "")
            .replace("_magazine", "")
            .replace("_imperfect", "")
            .replace("_nature", ""),
            [],
        )
        return universal + ai_artifacts + style_specific

    def _recommend_style(
        self,
        product: Product,
        reference_analysis: ReferenceAnalysis,
        brand: Brand | None = None,
    ) -> str:
        """Recomienda un estilo basado en la marca, categoría del producto y análisis de referencia.

        Orden de prioridad:
        1. Estilos preferidos de la marca (brand.style.preferred_design_styles)
        2. Estilos recomendados por categoría del producto
        3. Inferencia del mood de la referencia visual
        4. Default: lifestyle_warm
        """
        # 1. PRIORIDAD: Estilos preferidos de la marca
        if brand:
            brand_styles = brand.get_preferred_styles()
            if brand_styles:
                style = brand_styles[0]
                console.print(f"[dim]   Usando estilo preferido de marca: {style}[/dim]")
                return style

        # 2. Estilos recomendados por categoría del producto
        category = product.category.lower() if product.category else ""
        guidelines = self._get_category_guidelines(category)
        recommended = guidelines.get("recommended_styles", [])

        if recommended:
            return recommended[0]

        # 3. Fallback basado en el mood de la referencia
        mood = reference_analysis.style.mood.lower() if reference_analysis.style.mood else ""

        if any(word in mood for word in ["warm", "cozy", "inviting", "comfortable"]):
            return "lifestyle_warm"
        elif any(word in mood for word in ["clean", "minimal", "simple", "pure"]):
            return "minimal_clean"
        elif any(word in mood for word in ["dramatic", "bold", "striking", "editorial"]):
            return "editorial_magazine"
        elif any(word in mood for word in ["natural", "organic", "earthy", "rustic"]):
            return "authentic_imperfect"
        elif any(word in mood for word in ["fresh", "green", "botanical", "nature"]):
            return "biophilic_nature"

        return "lifestyle_warm"  # Default seguro para food/productos

    def _get_text_zone_description(self, brand: Brand, target_size: str) -> str:
        """Genera la descripción de zona de texto según la configuración de la marca."""
        text_zones = self.knowledge_base.get("prompt_structure", {}).get(
            "text_zone_descriptions", {}
        )

        price_pos = brand.text_overlay.price_badge.position
        title_pos = brand.text_overlay.title.position

        descriptions = []
        if price_pos in text_zones:
            descriptions.append(text_zones[price_pos])
        if title_pos in text_zones and title_pos != price_pos:
            descriptions.append(text_zones[title_pos])

        if not descriptions:
            if target_size == "feed":
                return "clear negative space in upper third for text and bottom-left for price"
            else:
                return "negative space in center-lower-third for text overlay"

        return ", ".join(descriptions)

    def build_prompt(
        self,
        reference_analysis: ReferenceAnalysis,
        brand: Brand,
        product: Product,
        target_size: str = "feed",
        style: DesignStyle = "auto",
    ) -> GenerationPrompt:
        """
        Construye un prompt optimizado con conocimiento de diseño.

        Args:
            reference_analysis: Análisis de la imagen de Pinterest
            brand: Configuración de la marca
            product: Información del producto
            target_size: "feed" (4:5) o "story" (9:16)
            style: Estilo de diseño a aplicar

        Returns:
            GenerationPrompt con el prompt optimizado
        """
        # Auto-seleccionar estilo si es necesario
        if style is None or style == "auto":
            style = self._recommend_style(product, reference_analysis, brand)
            console.print(f"[blue][Diseño][/blue] Estilo auto-seleccionado: {style}")

        console.print(f"[blue][Diseño] {self.name}:[/blue] Construyendo prompt estilo '{style}'...")

        # Obtener configuraciones
        style_config = self._get_style_config(style)
        default_negative = self._get_negative_prompts(style)

        # Extraer guías de composición de la referencia
        composition_guidance = self._extract_composition_guidance(reference_analysis)

        # Construir contexto visual de marca usando BrandTranslator
        brand_context = self.brand_translator.build_brand_context(brand)

        # Preparar contexto enriquecido para el LLM
        context = f"""
## Análisis de Referencia Visual (Pinterest):
{reference_analysis.to_prompt_context()}

## Guías de Composición Extraídas:
- Técnica: {composition_guidance.get('technique', 'rule_of_thirds')}
- Negative space: {composition_guidance.get('negative_space', 'balanced')}
- Ángulo de cámara: {composition_guidance.get('camera_angle', 'eye-level')}
- Profundidad de campo: {composition_guidance.get('depth_of_field', 'shallow')}

## Configuración de Marca:
- Nombre: {brand.name}
- Paleta: primary {brand.palette.primary}, secondary {brand.palette.secondary}, accent {brand.palette.accent}
- Mood de marca: {brand.get_mood_string()}
- Valores: {', '.join(brand.identity.values) if brand.identity.values else 'N/A'}
- Estilo fotográfico preferido: {brand.style.photography_style}

## Contexto Visual de Marca (TRADUCIDO):
{brand_context}

## Producto (la IMAGEN del producto se pasa directamente al generador):
- Nombre para mostrar: {product.name}
- Precio para mostrar: {product.price}
- Categoría: {product.category}
NOTA: NO describas el producto - su imagen real es la referencia visual.

## Estilo de Diseño: {style_config.get("name", style)}
- Descripción: {style_config.get("description", "")}
- Iluminación: {style_config.get("lighting", "natural")}
- Composición: {style_config.get("composition", "rule of thirds")}

## Especificaciones:
- Formato: {"Feed Instagram (4:5, 1080x1350)" if target_size == "feed" else "Story Instagram (9:16, 1080x1920)"}
- Safe zones: {"150px top, 200px bottom" if target_size == "feed" else "250px top, 340px bottom"}

## TEXTO INTEGRADO (MUY IMPORTANTE):
Generar DENTRO de la imagen:
- Nombre del producto: "{product.name}"
- Precio: "{product.price}"

ESTILO DEL PRECIO (badge/etiqueta):
- Crear un BADGE/ETIQUETA estilizada para el precio (no texto plano)
- Color de fondo del badge: {brand.text_overlay.price_badge.bg_color}
- Color del texto del precio: {brand.text_overlay.price_badge.text_color}
- Posición del badge: {brand.text_overlay.price_badge.position}
- Estilo: redondeado, moderno, que resalte pero no distraiga

Posición del nombre: {brand.text_overlay.title.position}
Copiar estilo tipográfico de la referencia Pinterest para el nombre.

## LOGO (si se proporciona imagen de logo):
- Insertar el logo de la marca en una esquina
- Posición preferida: top-right o top-left
- Tamaño: pequeño y discreto, no debe tapar el producto
- Mantener colores originales del logo

## Negative Prompts:
{", ".join(default_negative[:10])}

Generá el prompt en formato JSON. El producto viene de la imagen de referencia - enfocate en ESTILO, COMPOSICIÓN, ILUMINACIÓN y TEXTO.
IMPORTANTE: Usa las guías de composición extraídas y el contexto visual de marca traducido.
"""

        # Llamar a Claude con el system prompt de diseñador
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=DESIGNER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        # Parsear respuesta
        response_text = message.content[0].text

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError(f"No se pudo parsear la respuesta: {response_text}")

        # Validar y enriquecer el prompt
        prompt = data.get("prompt", "")
        
        # Refinar con validación multi-criterio (composición + marca + referencia)
        prompt = self._refine_prompt(prompt, reference_analysis, brand, target_size)
        
        # Validación básica adicional (lighting, quality)
        prompt = self._validate_and_enhance_prompt(prompt, style, target_size)

        # Construir GenerationPrompt
        params_data = data.get("params", {})
        params = GenerationParams(
            aspect_ratio=params_data.get(
                "aspect_ratio", "4:5" if target_size == "feed" else "9:16"
            ),
            quality=params_data.get("quality", "high"),
            size=params_data.get("size", "1080x1350" if target_size == "feed" else "1080x1920"),
        )

        generation_prompt = GenerationPrompt(
            prompt=prompt,
            visual_description=data.get("visual_description", ""),
            negative_prompt=data.get("negative_prompt", ", ".join(default_negative)),
            params=params,
        )

        # Mostrar rationale de diseño
        rationale = data.get("design_rationale", "")
        if rationale:
            console.print(f"[dim]   Decisión de diseño: {rationale[:100]}...[/dim]")

        console.print(f"[green][OK][/green] Prompt generado ({len(prompt)} chars)")
        console.print(f"[dim]   Estilo: {style} | Aspect ratio: {params.aspect_ratio}[/dim]")

        return generation_prompt

    def _extract_composition_guidance(self, reference_analysis: ReferenceAnalysis) -> dict:
        """Extrae principios de composición de la referencia.

        Args:
            reference_analysis: Análisis de la imagen de referencia

        Returns:
            Dict con guías de composición extraídas
        """
        guidance = {}

        # Técnica de composición
        if reference_analysis.layout.composition_technique:
            guidance["technique"] = reference_analysis.layout.composition_technique
        elif reference_analysis.layout.composition:
            # Inferir desde composition string
            comp_lower = reference_analysis.layout.composition.lower()
            if "rule of thirds" in comp_lower or "thirds" in comp_lower:
                guidance["technique"] = "rule_of_thirds"
            elif "golden" in comp_lower or "ratio" in comp_lower:
                guidance["technique"] = "golden_ratio"
            elif "centered" in comp_lower or "center" in comp_lower:
                guidance["technique"] = "centered"
            else:
                guidance["technique"] = "rule_of_thirds"  # Default seguro

        # Negative space
        if reference_analysis.layout.negative_space_distribution:
            guidance["negative_space"] = reference_analysis.layout.negative_space_distribution
        elif reference_analysis.layout.text_zones:
            # Inferir desde text_zones
            zones_str = " ".join(reference_analysis.layout.text_zones).lower()
            if "top" in zones_str:
                guidance["negative_space"] = "top"
            elif "bottom" in zones_str:
                guidance["negative_space"] = "bottom"
            else:
                guidance["negative_space"] = "balanced"

        # Camera angle
        if reference_analysis.layout.camera_angle:
            guidance["camera_angle"] = reference_analysis.layout.camera_angle

        # Depth of field
        if reference_analysis.layout.depth_of_field:
            guidance["depth_of_field"] = reference_analysis.layout.depth_of_field

        return guidance

    def _validate_composition(self, prompt: str, target_size: str) -> list[str]:
        """Valida que el prompt incluya composición profesional.

        Args:
            prompt: Prompt a validar
            target_size: "feed" o "story"

        Returns:
            Lista de elementos faltantes a agregar
        """
        required_elements = []
        prompt_lower = prompt.lower()

        # Verificar técnica de composición específica
        composition_techniques = [
            "rule of thirds",
            "golden ratio",
            "centered",
            "rule-of-thirds",
            "golden-ratio",
        ]
        has_technique = any(tech in prompt_lower for tech in composition_techniques)
        if not has_technique:
            required_elements.append("rule of thirds composition")

        # Verificar negative space (crítico para texto)
        if "negative space" not in prompt_lower:
            if target_size == "feed":
                required_elements.append("ample negative space in upper third and bottom area for text overlay")
            else:
                required_elements.append("ample negative space in center-lower-third for text overlay")

        # Verificar visual hierarchy
        hierarchy_keywords = ["focal point", "primary subject", "main subject", "visual hierarchy"]
        has_hierarchy = any(kw in prompt_lower for kw in hierarchy_keywords)
        if not has_hierarchy:
            required_elements.append("clear focal point with product as primary subject")

        return required_elements

    def _validate_brand_integration(self, prompt: str, brand: Brand) -> list[str]:
        """Valida que el prompt refleje la identidad de marca.

        Args:
            prompt: Prompt a validar
            brand: Objeto Brand con configuración

        Returns:
            Lista de elementos faltantes relacionados con marca
        """
        missing = []
        prompt_lower = prompt.lower()

        # Verificar colores de marca
        brand_colors = [
            brand.palette.primary.lower(),
            brand.palette.secondary.lower(),
        ]
        if brand.palette.accent:
            brand_colors.append(brand.palette.accent.lower())

        # Buscar menciones de colores (hex o descripciones)
        color_mentioned = False
        for color in brand_colors:
            # Buscar hex code o variaciones
            if color in prompt_lower or color.replace("#", "") in prompt_lower:
                color_mentioned = True
                break

        if not color_mentioned:
            missing.append(f"subtle use of brand colors ({brand.palette.primary}) in secondary elements")

        # Verificar mood de marca traducido a visual
        if brand.style.mood:
            mood_keywords = self.brand_translator.get_mood_keywords_flat(brand.style.mood)
            mood_mentioned = any(kw in prompt_lower for kw in mood_keywords)
            if not mood_mentioned:
                # Agregar primeros 2 keywords de mood
                top_mood_keywords = mood_keywords[:2]
                if top_mood_keywords:
                    missing.append(f"{', '.join(top_mood_keywords)} atmosphere")

        # Verificar valores de marca
        if brand.identity.values:
            values_keywords = self.brand_translator.values_to_visual(brand.identity.values)
            values_mentioned = any(kw in prompt_lower for kw in values_keywords)
            if not values_mentioned and values_keywords:
                missing.append(f"{values_keywords[0]}")  # Agregar primer keyword de values

        return missing

    def _validate_reference_usage(self, prompt: str, reference_analysis: ReferenceAnalysis) -> list[str]:
        """Valida que el prompt use correctamente la referencia.

        Args:
            prompt: Prompt a validar
            reference_analysis: Análisis de referencia

        Returns:
            Lista de mejoras relacionadas con uso de referencia
        """
        improvements = []
        prompt_lower = prompt.lower()

        # Verificar que se mencione el estilo/mood de la referencia
        if reference_analysis.style.mood and reference_analysis.style.mood.lower() not in prompt_lower:
            # No es crítico, pero puede mejorar coherencia
            pass

        # Verificar uso de composición de referencia
        if reference_analysis.layout.composition_technique:
            technique = reference_analysis.layout.composition_technique.replace("_", " ")
            if technique not in prompt_lower:
                improvements.append(f"apply {technique} composition technique from reference")

        return improvements

    def _refine_prompt(
        self,
        prompt: str,
        reference_analysis: ReferenceAnalysis,
        brand: Brand,
        target_size: str,
    ) -> str:
        """Refina el prompt con validación multi-criterio.

        Args:
            prompt: Prompt base generado por Claude
            reference_analysis: Análisis de referencia
            brand: Configuración de marca
            target_size: "feed" o "story"

        Returns:
            Prompt refinado con mejoras aplicadas
        """
        # 1. Validar composición
        composition_fixes = self._validate_composition(prompt, target_size)

        # 2. Validar integración de marca
        brand_fixes = self._validate_brand_integration(prompt, brand)

        # 3. Validar uso de referencia
        reference_fixes = self._validate_reference_usage(prompt, reference_analysis)

        # 4. Aplicar mejoras
        all_fixes = composition_fixes + brand_fixes + reference_fixes
        if all_fixes:
            fixes_str = ", ".join(all_fixes)
            prompt = f"{prompt}, {fixes_str}"
            console.print(f"[yellow][Refinado][/yellow] Agregados {len(all_fixes)} elementos de mejora")

        return prompt

    def _validate_and_enhance_prompt(self, prompt: str, style: str, target_size: str) -> str:
        """Valida que el prompt tenga elementos esenciales y los agrega si faltan.

        Este método ahora es un wrapper que mantiene compatibilidad.
        La validación avanzada se hace en _refine_prompt().
        """
        essential_elements = {
            "lighting": ["lighting", "light", "illumination", "lit"],
            "quality": ["8K", "sharp focus", "professional", "commercial", "high quality"],
        }

        missing = []
        prompt_lower = prompt.lower()

        for element, keywords in essential_elements.items():
            if not any(kw.lower() in prompt_lower for kw in keywords):
                missing.append(element)

        # Agregar elementos faltantes básicos
        additions = []
        if "lighting" in missing:
            additions.append("soft natural lighting")
        if "quality" in missing:
            additions.append("8K detail, sharp focus, professional quality")

        if additions:
            prompt = f"{prompt}, {', '.join(additions)}"
            console.print(f"[dim]   [+] Agregados básicos: {', '.join(missing)}[/dim]")

        return prompt

    def build_prompt_batch(
        self,
        reference_analyses: list[ReferenceAnalysis],
        brand: Brand,
        product: Product,
        target_size: str = "feed",
        style: DesignStyle = "auto",
    ) -> list[GenerationPrompt]:
        """
        Construye múltiples prompts para diferentes referencias.

        Args:
            reference_analyses: Lista de análisis de referencias
            brand: Configuración de la marca
            product: Información del producto
            target_size: "feed" o "story"
            style: Estilo de diseño

        Returns:
            Lista de GenerationPrompt
        """
        results = []
        for i, analysis in enumerate(reference_analyses, 1):
            console.print(f"\n[dim]Diseño {i}/{len(reference_analyses)}[/dim]")
            results.append(self.build_prompt(analysis, brand, product, target_size, style))
        return results

    def get_available_styles(self) -> list[dict]:
        """Retorna los estilos disponibles con sus descripciones."""
        styles = self.knowledge_base.get("styles", {})
        return [
            {
                "key": key,
                "name": config.get("name", key),
                "description": config.get("description", ""),
            }
            for key, config in styles.items()
        ]
