"""
StrategistAgent - Marketing/Creative Director for content planning.

This agent interprets natural language requests and creates structured ContentPlans.
It uses the Knowledge Base for marketing insights and can search Pinterest for references.
Orchestrates the full workflow: Pinterest search → Plan creation → Pipeline execution.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from anthropic import Anthropic

from ..models.brand import Brand
from ..models.campaign_plan import CampaignPlan
from ..models.campaign_style import (
    CampaignStyleGuide,
    PriceBadgeStyle,
    get_preset,
)
from ..models.plan import ContentIntent, ContentPlan, ContentPlanItem
from ..services.mcp_client import MCPClientService
from .base import parse_data_url

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Loads and queries the marketing knowledge base."""

    def __init__(self, knowledge_dir: Path = Path("knowledge")):
        self.knowledge_dir = knowledge_dir
        self._calendar: dict | None = None
        self._insights: dict | None = None
        self._copy_templates: dict | None = None
        self._design_styles: dict | None = None

    @property
    def calendar(self) -> dict:
        """Load marketing calendar."""
        if self._calendar is None:
            path = self.knowledge_dir / "marketing_calendar.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._calendar = json.load(f)
            else:
                self._calendar = {}
        return self._calendar

    @property
    def insights(self) -> dict:
        """Load industry insights."""
        if self._insights is None:
            path = self.knowledge_dir / "industry_insights.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._insights = json.load(f)
            else:
                self._insights = {}
        return self._insights

    @property
    def copy_templates(self) -> dict:
        """Load copy templates."""
        if self._copy_templates is None:
            path = self.knowledge_dir / "copy_templates.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._copy_templates = json.load(f)
            else:
                self._copy_templates = {}
        return self._copy_templates

    @property
    def design_styles(self) -> dict:
        """Load design styles."""
        if self._design_styles is None:
            path = self.knowledge_dir / "design_2026.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._design_styles = json.load(f)
            else:
                self._design_styles = {}
        return self._design_styles

    def get_industry_info(self, industry: str) -> dict:
        """Get insights for a specific industry."""
        return self.insights.get("industries", {}).get(industry, {})

    def get_upcoming_dates(self, industry: str, month: str | None = None) -> list:
        """Get upcoming marketing dates for an industry."""
        if month is None:
            month = datetime.now().strftime("%B").lower()

        dates = []
        global_dates = self.calendar.get("global_dates", {})

        # Map English month names to Spanish
        month_map = {
            "january": "enero",
            "february": "febrero",
            "march": "marzo",
            "april": "abril",
            "may": "mayo",
            "june": "junio",
            "july": "julio",
            "august": "agosto",
            "september": "septiembre",
            "october": "octubre",
            "november": "noviembre",
            "december": "diciembre",
        }
        month_es = month_map.get(month.lower(), month.lower())

        if month_es in global_dates:
            for date_info in global_dates[month_es]:
                industries = date_info.get("industries", [])
                if "all" in industries or industry in industries:
                    dates.append(date_info)

        return dates

    def get_recommended_styles(self, industry: str) -> list[str]:
        """Get recommended design styles for an industry."""
        industry_info = self.get_industry_info(industry)
        return industry_info.get("recommended_styles", ["minimal_clean"])

    def get_copy_template(self, objective: str) -> dict:
        """Get copy template for an objective."""
        templates = self.copy_templates.get("templates_by_objective", {})
        return templates.get(objective, {})

    def get_style_config(self, style_name: str) -> dict:
        """Get style configuration from design knowledge base."""
        styles = self.design_styles.get("styles", {})
        return styles.get(style_name, {})

    def get_lighting_config(self, lighting_name: str) -> dict:
        """Get lighting configuration from design knowledge base."""
        lighting_styles = self.design_styles.get("lighting_styles", {})
        return lighting_styles.get(lighting_name, {})

    def get_category_guidelines(self, category: str) -> dict:
        """Get category-specific guidelines from design knowledge base."""
        guidelines = self.design_styles.get("category_guidelines", {})
        return guidelines.get(category, {})

    def get_negative_prompts(self, style: str | None = None) -> list[str]:
        """Get negative prompts from design knowledge base."""
        negatives = self.design_styles.get("negative_prompts", {})
        universal = negatives.get("universal", [])
        ai_artifacts = negatives.get("ai_artifacts", [])

        result = universal + ai_artifacts

        # Add style-specific negatives
        if style:
            style_specific = negatives.get("style_specific", {})
            style_negatives = style_specific.get(style, [])
            result.extend(style_negatives)

        return result

    def get_trend_additions(self, trend_name: str) -> list[str]:
        """Get trend-specific prompt additions."""
        trends = self.design_styles.get("trends_2026", {})
        trend = trends.get(trend_name, {})
        return trend.get("prompt_additions", [])


class StrategistAgent:
    """
    Marketing strategist agent that interprets requests and creates content plans.

    Responsibilities:
    - Understand natural language requests
    - Consult knowledge base for context
    - Create structured ContentPlans
    - Suggest Pinterest search queries
    - Provide copy suggestions
    """

    name = "StrategistAgent"
    description = "Marketing expert that creates content plans from natural language"

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        knowledge_dir: Path = Path("knowledge"),
    ):
        self.model = model
        self.knowledge = KnowledgeBase(knowledge_dir)
        self.client: Anthropic | None = None
        self.mcp_service: MCPClientService | None = None

    def _get_client(self) -> Anthropic | None:
        """Lazy initialization of Anthropic client."""
        if self.client is None:
            try:
                import os

                from dotenv import load_dotenv

                # Load .env file if not already loaded
                load_dotenv()

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.info("ANTHROPIC_API_KEY not set, running in fallback mode")
                    return None
                self.client = Anthropic(api_key=api_key)
            except Exception as e:
                logger.warning(f"Anthropic client not available: {e}")
                logger.info("Running in fallback mode without AI capabilities")
                return None
        return self.client

    def _get_mcp_service(self) -> MCPClientService | None:
        """Lazy initialization of MCP service."""
        if self.mcp_service is None:
            try:
                self.mcp_service = MCPClientService()
            except Exception as e:
                logger.warning(f"MCP service not available: {e}")
                return None
        return self.mcp_service

    def _should_search_pinterest(self, message: str) -> bool:
        """Detect if user wants to search Pinterest."""
        pinterest_keywords = [
            "busca en pinterest",
            "buscar en pinterest",
            "pinterest",
            "referencias de pinterest",
            "imágenes de pinterest",
            "ideas de pinterest",
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in pinterest_keywords)

    async def _search_pinterest_for_references(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search Pinterest for reference images using MCP.

        Args:
            query: Search query
            limit: Number of results

        Returns:
            List of Pinterest results with URLs and metadata
        """
        service = self._get_mcp_service()
        if not service:
            logger.warning("MCP service not available, cannot search Pinterest")
            return []

        try:
            results = await service.search_pinterest(query, limit=limit, download=True)
            logger.info(f"Pinterest search: {len(results)} results for '{query}'")
            return results if results else []
        except Exception as e:
            logger.error(f"Pinterest search failed: {e}")
            return []

    def create_plan(
        self,
        prompt: str,
        brand: Brand,
        brand_dir: Path,
        campaign: str | None = None,
        pinterest_results: list[dict] | None = None,
    ) -> ContentPlan:
        """
        Create a content plan from a natural language prompt.

        Args:
            prompt: User's natural language request
            brand: Brand configuration
            brand_dir: Path to brand directory
            campaign: Optional campaign name
            pinterest_results: Optional Pinterest search results to use as references

        Returns:
            ContentPlan ready for approval and execution
        """
        logger.info(f"Creating plan for: {prompt[:50]}...")

        # Get industry context
        industry = brand.industry or "retail"
        industry_info = self.knowledge.get_industry_info(industry)
        recommended_styles = self.knowledge.get_recommended_styles(industry)

        # Analyze intent from prompt
        intent = self._analyze_intent(prompt, industry_info)

        # plan.brand tiene que ser el SLUG (carpeta en brands/) para que execute_generation encuentre brand_dir
        plan = ContentPlan(
            brand=brand_dir.name,
            campaign=campaign,
            intent=intent,
        )

        enriched = self._enrich_brand_context(brand, brand_dir)

        # Generate plan items (cada item.product = slug de producto existente con fotos)
        items = self._generate_items(
            prompt=prompt,
            intent=intent,
            brand=brand,
            recommended_styles=recommended_styles,
            industry_info=industry_info,
            pinterest_results=pinterest_results,
            enriched_context=enriched,
        )

        for item in items:
            plan.items.append(item)

        plan._update_cost()

        logger.info(f"Plan created: {plan.id} with {len(plan.items)} items")
        return plan

    def plan_campaign(
        self,
        prompt: str,
        brand: Brand,
        brand_dir: Path,
        days: int = 7,
        products: list[str] | None = None,
    ) -> "CampaignPlan":
        """
        Crea un CampaignPlan estructurado para campañas de varios días.

        Args:
            prompt: Descripción de la campaña (ej: "Black Friday 7 días")
            brand: Configuración de la marca
            brand_dir: Path al directorio de la marca
            days: Número de días de la campaña
            products: Lista de slugs de productos (si no se especifica, usa todos)

        Returns:
            CampaignPlan listo para ejecutar con CampaignPipeline
        """
        from ..models.campaign_plan import CampaignPlan, DayPlan, VisualCoherence

        logger.info(f"Creating campaign plan: {prompt[:50]}... ({days} days)")

        # Detectar tipo de campaña del prompt
        prompt_lower = prompt.lower()
        campaign_name = "Campaña"
        base_style = "bold_contrast"
        color_scheme = ["#000000", "#FF0000"]

        # Detectar ocasión y ajustar estilo
        if "black friday" in prompt_lower:
            campaign_name = "Black Friday"
            base_style = "bold_contrast"
            color_scheme = ["#000000", "#FFD700", "#FF0000"]
        elif "cyber monday" in prompt_lower:
            campaign_name = "Cyber Monday"
            base_style = "tech_neon"
            color_scheme = ["#0D0D0D", "#00FFFF", "#FF00FF"]
        elif "navidad" in prompt_lower or "christmas" in prompt_lower:
            campaign_name = "Navidad"
            base_style = "festive_warm"
            color_scheme = ["#C41E3A", "#228B22", "#FFD700"]
        elif "verano" in prompt_lower or "summer" in prompt_lower:
            campaign_name = "Verano"
            base_style = "bright_fresh"
            color_scheme = ["#00CED1", "#FFD700", "#FF6B6B"]
        elif "san valentín" in prompt_lower or "valentine" in prompt_lower:
            campaign_name = "San Valentín"
            base_style = "romantic_soft"
            color_scheme = ["#FF69B4", "#FFB6C1", "#DC143C"]

        # Obtener productos disponibles
        enriched = self._enrich_brand_context(brand, brand_dir)
        available_products = [
            p["slug"] for p in enriched.get("products", []) if p.get("has_photos")
        ]

        if products:
            # Filtrar solo los especificados que existen
            campaign_products = [p for p in products if p in available_products]
        else:
            campaign_products = available_products

        if not campaign_products:
            logger.warning("No products with photos found for campaign")
            campaign_products = ["producto-general"]

        # Definir temas por día según duración
        if days == 7:
            # Campaña de semana completa
            day_themes = [
                ("teaser", "low", "Misterio, anticipación, siluetas oscuras"),
                ("countdown", "low", "Countdown 5 días, revelando hints"),
                ("reveal", "medium", "Primera revelación de ofertas"),
                ("anticipation", "medium", "Build-up, mostrar productos"),
                ("main_offer", "high", "Día principal, todas las ofertas"),
                ("extended", "critical", "Últimas horas, urgencia máxima"),
                ("closing", "high", "Cierre, agradecimiento, última chance"),
            ]
        elif days == 3:
            day_themes = [
                ("teaser", "medium", "Anticipación y misterio"),
                ("main_offer", "high", "Ofertas principales"),
                ("last_chance", "critical", "Última oportunidad"),
            ]
        elif days == 5:
            day_themes = [
                ("teaser", "low", "Anticipación"),
                ("countdown", "medium", "Countdown"),
                ("main_offer", "high", "Día principal"),
                ("extended", "high", "Extendido"),
                ("closing", "critical", "Cierre"),
            ]
        else:
            # Generar temas genéricos
            day_themes = []
            for i in range(days):
                if i == 0:
                    day_themes.append(("teaser", "low", "Inicio de campaña"))
                elif i == days - 1:
                    day_themes.append(("closing", "critical", "Cierre de campaña"))
                elif i == days // 2:
                    day_themes.append(("main_offer", "high", "Día principal"))
                else:
                    day_themes.append(("main_offer", "medium", f"Día {i + 1}"))

        # Crear DayPlans
        day_plans = []
        for i, (theme, urgency, visual_dir) in enumerate(day_themes):
            # Rotar productos entre días
            day_products = [campaign_products[i % len(campaign_products)]]
            # En días principales, incluir más productos
            if theme in ["main_offer", "extended"] and len(campaign_products) > 1:
                day_products = campaign_products

            day_plan = DayPlan(
                day=i + 1,
                theme=theme,
                products=day_products,
                visual_direction=visual_dir,
                urgency_level=urgency,
                size="feed",  # Default, puede variarse
            )
            day_plans.append(day_plan)

        # Crear coherencia visual
        visual_coherence = VisualCoherence(
            base_style=base_style,
            color_scheme=color_scheme,
            typography_style="bold, impactful",
            mood_progression=["mysterious", "exciting", "urgent", "celebratory"],
            consistent_elements=["logo_position", "price_badge_style", "brand_colors"],
        )

        # Crear CampaignPlan
        campaign_plan = CampaignPlan(
            name=campaign_name,
            brand_slug=brand_dir.name,
            days=day_plans,
            visual_coherence=visual_coherence,
        )

        logger.info(
            f"Campaign plan created: {campaign_plan.name} with {len(campaign_plan.days)} days, "
            f"estimated cost ${campaign_plan.estimated_cost_usd:.2f}"
        )

        # Crear StyleGuide inteligente basado en knowledge base
        style_guide = self._create_style_guide(
            occasion=campaign_name.lower().replace(" ", "_"),
            brand=brand,
            industry=brand.industry or "retail",
            campaign_name=campaign_name,
            color_scheme=color_scheme,
        )
        campaign_plan.style_guide = style_guide

        logger.info(f"StyleGuide created: {style_guide.name} (base: {style_guide.base_style})")

        return campaign_plan

    def _create_style_guide(
        self,
        occasion: str,
        brand: Brand,
        industry: str,
        campaign_name: str = "",
        color_scheme: list[str] | None = None,
    ) -> CampaignStyleGuide:
        """Crea un CampaignStyleGuide inteligente basado en el knowledge base.

        Consulta:
        - design_2026.json para estilos, iluminación, trends
        - category_guidelines para la industria
        - Presets para ocasiones (black_friday, christmas, etc.)

        Args:
            occasion: Código de la ocasión (black_friday, christmas, etc.)
            brand: Configuración de la marca
            industry: Industria/categoría del negocio
            campaign_name: Nombre de la campaña
            color_scheme: Esquema de colores (si no viene, se usa el del preset/marca)

        Returns:
            CampaignStyleGuide completamente configurado
        """
        logger.info(f"Creating StyleGuide for {occasion}, industry: {industry}")

        # 1. Intentar cargar preset de ocasión
        preset_occasions = [
            "black_friday",
            "christmas",
            "summer_promo",
            "valentines",
            "cyber_monday",
        ]
        normalized_occasion = occasion.lower().replace(" ", "_")

        if normalized_occasion in preset_occasions:
            style_guide = get_preset(normalized_occasion)
            logger.info(f"Using preset for {normalized_occasion}")
        else:
            # Crear desde cero
            style_guide = CampaignStyleGuide(
                name=f"{campaign_name} Style Guide",
                occasion=normalized_occasion,
            )

        # 2. Consultar category_guidelines del knowledge base
        category_guidelines = self.knowledge.get_category_guidelines(industry)
        if category_guidelines:
            logger.info(f"Applying category guidelines for {industry}")

            # Estilo recomendado para la categoría
            recommended_styles = category_guidelines.get("recommended_styles", [])
            if recommended_styles and not style_guide.base_style:
                style_guide.base_style = recommended_styles[0]

            # Obtener configuración completa del estilo
            style_config = self.knowledge.get_style_config(style_guide.base_style)
            if style_config:
                style_guide.base_style_prompt = style_config.get("prompt_template", "")

                # Iluminación del estilo
                lighting_name = style_config.get("lighting", "soft_studio")
                lighting_config = self.knowledge.get_lighting_config(lighting_name)
                if lighting_config:
                    style_guide.lighting_style = lighting_name
                    style_guide.lighting_prompt = lighting_config.get("prompt", "")

                # Background del estilo
                backgrounds = style_config.get("background", [])
                if backgrounds:
                    style_guide.background_prompt = (
                        backgrounds[0] if isinstance(backgrounds, list) else backgrounds
                    )

            # Props y adiciones recomendadas
            prompt_additions = category_guidelines.get("prompt_additions", [])
            if prompt_additions:
                style_guide.atmosphere = ", ".join(prompt_additions[:3])

            # Cosas a evitar de la categoría
            avoid = category_guidelines.get("avoid", [])
            if avoid:
                style_guide.forbidden_elements = list(set(style_guide.forbidden_elements + avoid))

        # 3. Aplicar colores de la marca si no vienen del preset
        if color_scheme:
            style_guide.color_scheme = color_scheme
            if len(color_scheme) >= 1:
                style_guide.primary_color = color_scheme[0]
            if len(color_scheme) >= 2:
                style_guide.accent_color = color_scheme[1]
            if len(color_scheme) >= 3:
                style_guide.highlight_color = color_scheme[2]
        elif brand.palette:
            # Usar paleta de la marca
            style_guide.primary_color = brand.palette.primary
            style_guide.accent_color = brand.palette.secondary
            if brand.palette.accent:
                style_guide.highlight_color = brand.palette.accent
            style_guide.color_scheme = [
                brand.palette.primary,
                brand.palette.secondary,
                brand.palette.accent or "#FFFFFF",
            ]

        # 4. Configurar badge de precio según la marca
        if brand.text_overlay and brand.text_overlay.price_badge:
            badge_config = brand.text_overlay.price_badge
            style_guide.price_badge = PriceBadgeStyle(
                shape="circular",  # Default
                bg_color=badge_config.bg_color,
                text_color=badge_config.text_color,
                position=badge_config.position,
                size="medium",
            )

        # 5. Configurar logo según la marca
        if brand.text_overlay and brand.text_overlay.logo:
            style_guide.logo_placement = brand.text_overlay.logo.position or "top-right"
            style_guide.logo_size = brand.text_overlay.logo.size or "small"
            style_guide.logo_style = "white version, subtle"

        # 6. Aplicar negative prompts del knowledge base
        negative_prompts = self.knowledge.get_negative_prompts(style_guide.base_style)
        if negative_prompts:
            style_guide.negative_prompts = list(
                set(style_guide.negative_prompts + negative_prompts)
            )

        # 7. Aplicar trends 2026 según la ocasión/industria
        trend_map = {
            "food": "authentic_imperfect",
            "beverages": "warm_tones",
            "food_restaurant": "authentic_imperfect",
            "retail": "tactile_craft",
            "pharmacy": "biophilic_design",
            "wine_spirits": "warm_tones",
        }
        trend_name = trend_map.get(industry, "warm_tones")
        trend_additions = self.knowledge.get_trend_additions(trend_name)
        if trend_additions:
            # Agregar al atmosphere
            current = style_guide.atmosphere
            style_guide.atmosphere = f"{current}, {', '.join(trend_additions[:2])}"

        # 8. Configurar quality tags del knowledge base
        quality_tags = self.knowledge.design_styles.get("prompt_structure", {}).get(
            "quality_tags", []
        )
        if quality_tags:
            style_guide.quality_tags = quality_tags

        # 9. Nombre final
        style_guide.name = f"{campaign_name} Style Guide"

        logger.info(
            f"StyleGuide created: style={style_guide.base_style}, "
            f"lighting={style_guide.lighting_style}, colors={style_guide.color_scheme[:2]}"
        )

        return style_guide

    def _parse_campaign_products(self, prompt: str, enriched_context: dict) -> list[dict]:
        """
        Parse campaign products and prices from prompt.

        Detects patterns like:
        - "para sprite, coca, fanta y 7up"
        - "precios: $1.99, $2.50, $1.50, $1.99"

        Returns:
            List of dicts with {slug, price_override}
        """
        import re

        prompt_lower = prompt.lower()
        products = enriched_context.get("products", [])

        # DEBUG: Log what we're working with
        logger.info(f"[CAMPAIGN DEBUG] Prompt: {prompt}")
        logger.info(f"[CAMPAIGN DEBUG] Found {len(products)} products in enriched_context")
        for p in products:
            logger.info(
                f"[CAMPAIGN DEBUG] Product: {p.get('name')} (slug: {p.get('slug')}, has_photos: {p.get('has_photos')})"
            )

        # Extract product names from prompt
        detected_products = []
        for p in products:
            slug = p.get("slug", "")
            name = p.get("name", "")
            # Check if product is mentioned in prompt
            if slug.lower() in prompt_lower or name.lower() in prompt_lower:
                logger.info(f"[CAMPAIGN DEBUG] ✓ Detected product: {name} ({slug})")
                detected_products.append({"slug": slug, "name": name, "price_override": None})
            else:
                logger.info(f"[CAMPAIGN DEBUG] ✗ Product not in prompt: {name} ({slug})")

        # Extract prices from prompt
        # Patterns: "$1.99", "1.99", "$1,99", "precios: X, Y, Z"
        price_patterns = [
            r"\$\s*(\d+[.,]\d{2})",  # $1.99 or $1,99
            r"(?:precio|price)s?\s*:?\s*([0-9,.\s$]+)",  # precios: 1.99, 2.50
        ]

        prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            for match in matches:
                # Extract individual prices from match
                price_nums = re.findall(r"(\d+[.,]\d{2})", match)
                for price in price_nums:
                    normalized = price.replace(",", ".")
                    prices.append(f"${normalized}")

        # Map prices to products (in order)
        for i, product in enumerate(detected_products):
            if i < len(prices):
                product["price_override"] = prices[i]

        logger.info(f"[CAMPAIGN DEBUG] Extracted {len(prices)} prices: {prices}")
        logger.info(f"[CAMPAIGN DEBUG] Detected {len(detected_products)} products with prices")
        logger.info(f"[CAMPAIGN DEBUG] Is campaign? {len(detected_products) > 1}")

        return detected_products if len(detected_products) > 1 else []

    def _analyze_intent(
        self,
        prompt: str,
        industry_info: dict,
    ) -> ContentIntent:
        """Analyze user prompt to extract intent."""
        prompt_lower = prompt.lower()

        # Simple keyword-based intent detection
        # TODO: Use LLM for more sophisticated analysis
        objective: Literal["promocionar", "informar", "engagement", "branding", "lanzamiento"] = (
            "promocionar"
        )

        if any(kw in prompt_lower for kw in ["lanzar", "nuevo", "novedad", "estreno"]):
            objective = "lanzamiento"
        elif any(kw in prompt_lower for kw in ["promo", "oferta", "descuento", "2x1", "sale"]):
            objective = "promocionar"
        elif any(kw in prompt_lower for kw in ["info", "tip", "consejo", "sabías"]):
            objective = "informar"
        elif any(kw in prompt_lower for kw in ["pregunta", "interacción", "engagement"]):
            objective = "engagement"
        elif any(kw in prompt_lower for kw in ["marca", "historia", "valores"]):
            objective = "branding"

        # Detect occasion
        occasion = None
        occasions = [
            ("día del padre", "dia_del_padre"),
            ("día de la madre", "dia_de_la_madre"),
            ("san valentín", "san_valentin"),
            ("navidad", "navidad"),
            ("black friday", "black_friday"),
            ("año nuevo", "año_nuevo"),
        ]
        for keyword, code in occasions:
            if keyword in prompt_lower:
                occasion = code
                break

        # Detect tone
        tone = ["profesional"]
        if any(kw in prompt_lower for kw in ["urgente", "rápido", "ahora"]):
            tone.append("urgente")
        if any(kw in prompt_lower for kw in ["elegante", "premium", "exclusivo"]):
            tone.append("elegante")
        if any(kw in prompt_lower for kw in ["divertido", "fresco", "joven"]):
            tone.append("divertido")

        # Detect constraints
        constraints = []
        if "sin texto" in prompt_lower or "no texto" in prompt_lower:
            constraints.append("sin_texto")
        if "vertical" in prompt_lower or "story" in prompt_lower:
            constraints.append("vertical")
        if "horizontal" in prompt_lower or "feed" in prompt_lower:
            constraints.append("horizontal")

        return ContentIntent(
            objective=objective,
            occasion=occasion,
            tone=tone,
            constraints=constraints,
        )

    def _generate_items(
        self,
        prompt: str,
        intent: ContentIntent,
        brand: Brand,
        recommended_styles: list[str],
        industry_info: dict,
        pinterest_results: list[dict] | None = None,
        enriched_context: dict | None = None,
    ) -> list[ContentPlanItem]:
        """Generate plan items. Cada item.product debe ser el slug de un producto existente con fotos."""
        items = []
        prompt_lower = prompt.lower()

        # Check if this is a multi-product campaign
        campaign_products = self._parse_campaign_products(prompt, enriched_context or {})

        # Get copy template
        copy_template = self.knowledge.get_copy_template(intent.objective)
        template_structures = copy_template.get("structures", [])

        # Determine sizes (default: feed only for campaigns to keep it simple)
        sizes: list[Literal["feed", "story"]] = ["feed"]
        if "vertical" in intent.constraints:
            sizes = ["story"]
        elif "horizontal" not in intent.constraints and not campaign_products:
            # Only generate multiple sizes if NOT a campaign (to avoid 8 images for 4 products)
            sizes = ["feed", "story"]

        # Get preferred style (SAME for all products in campaign)
        brand_styles = brand.get_preferred_styles()
        style = (
            brand_styles[0]
            if brand_styles
            else (recommended_styles[0] if recommended_styles else "minimal_clean")
        )

        # Build reference query (shared for all items)
        query_parts = []
        if brand.industry:
            query_parts.append(brand.industry.replace("_", " "))
        if intent.occasion:
            query_parts.append(intent.occasion.replace("_", " "))
        query_parts.append(style.replace("_", " "))
        query_parts.append("instagram")
        reference_query = " ".join(query_parts)

        # Extract reference URLs and local paths (shared for all items)
        reference_urls: list[str] = []
        reference_local_paths: list[str] = []
        if pinterest_results:
            for result in pinterest_results[:3]:
                if isinstance(result, dict):
                    url = result.get("url") or result.get("image_url") or result.get("pin_url")
                    if url:
                        reference_urls.append(url)
                    # Get local path if available (MCP downloads to references/)
                    local_path = result.get("local_path")
                    if local_path:
                        reference_local_paths.append(local_path)

        # Detect variants count
        variants_count = 1
        if any(
            kw in prompt_lower
            for kw in ["variantes", "variants", "opciones", "varios", "múltiples"]
        ):
            import re

            numbers = re.findall(r"\d+", prompt)
            variants_count = min(int(numbers[0]), 10) if numbers else 4

        if campaign_products:
            # CAMPAIGN MODE: Create 1 item per product (all with same style/reference)
            for size in sizes:
                for campaign_prod in campaign_products:
                    copy_suggestion = self._generate_copy_suggestion(
                        prompt=prompt,
                        intent=intent,
                        template_structures=template_structures,
                        brand=brand,
                    )

                    item = ContentPlanItem(
                        product=campaign_prod["slug"],
                        size=size,
                        style=style,
                        copy_suggestion=copy_suggestion,
                        reference_query=reference_query,
                        reference_urls=reference_urls,
                        reference_local_paths=reference_local_paths,
                        variants_count=variants_count,
                        price_override=campaign_prod.get("price_override"),
                    )
                    items.append(item)
        else:
            # SINGLE PRODUCT MODE (legacy behavior)
            # Elegir producto: el pipeline necesita un slug que exista en products/{marca}/ con fotos
            product_slug = "producto-general"
            products = (enriched_context or {}).get("products", [])
            with_photos = [p for p in products if p.get("has_photos")]
            if with_photos:
                # Intentar matchear con el prompt
                for p in with_photos:
                    if (
                        p.get("slug", "").lower() in prompt_lower
                        or (p.get("name") or "").lower() in prompt_lower
                    ):
                        product_slug = p["slug"]
                        break
                else:
                    product_slug = with_photos[0]["slug"]

            for size in sizes:
                copy_suggestion = self._generate_copy_suggestion(
                    prompt=prompt,
                    intent=intent,
                    template_structures=template_structures,
                    brand=brand,
                )

                item = ContentPlanItem(
                    product=product_slug,
                    size=size,
                    style=style,
                    copy_suggestion=copy_suggestion,
                    reference_query=reference_query,
                    reference_urls=reference_urls,
                    reference_local_paths=reference_local_paths,
                    variants_count=variants_count,
                )
                items.append(item)

        return items

    def _generate_copy_suggestion(
        self,
        prompt: str,
        intent: ContentIntent,
        template_structures: list[dict],
        brand: Brand,
    ) -> str:
        """Generate a copy suggestion based on intent and templates."""
        if not template_structures:
            return f"[Copy basado en: {prompt[:100]}]"

        # Use first template structure as base
        template = template_structures[0]
        example = template.get("example", "")

        if example:
            return f"Sugerencia (editar): {example[:200]}"

        return f"[Copy sugerido para {intent.objective}]"

    def chat(
        self,
        message: str,
        brand: Brand | None = None,
        context: list[dict] | None = None,
        images: list[str] | None = None,
        workflow_mode: str = "plan",
        pinterest_results: list[dict] | None = None,
        brand_slug: str | None = None,
    ) -> tuple[str, ContentPlan | None]:
        """
        Chat with the strategist agent.

        Args:
            message: User message
            brand: Optional brand context
            context: Previous conversation context
            images: Optional list of base64 data URLs (frontend uploads) to use as reference
            workflow_mode: "plan" or "build" - affects behavior and auto-approval
            brand_slug: Slug de la marca (carpeta en brands/). Si se pasa, se usa para
                resolver brand_dir y productos. Lo debe enviar la API desde el request.

        Returns:
            Tuple of (response text, optional ContentPlan)
        """
        # Detect if message indicates BUILD mode (even if workflow_mode is plan)
        is_build_mode = workflow_mode == "build" or message.startswith("[MODO BUILD]")
        if message.startswith("[MODO BUILD]"):
            message = message.replace("[MODO BUILD]", "").strip()

        # Resolver brand_dir: el pipeline usa brands/{slug}. Preferir brand_slug (viene del request).
        brand_dir = None
        try:
            from ..api.config import settings

            base = Path(settings.BRANDS_DIR)
        except Exception:
            base = Path("brands")

        if brand_slug:
            brand_dir = base / brand_slug
            if not brand_dir.exists():
                brand_dir = None
        if brand and not brand_dir:
            for p in [base / brand.name, Path("brands") / brand.name, Path(".") / brand.name]:
                if p.exists():
                    brand_dir = p
                    break

        system_prompt = self._build_system_prompt(brand, brand_dir)

        # Enhance message if Pinterest results were found
        enhanced_message = message
        if pinterest_results:
            enhanced_message = (
                f"{message}\n\n[Nota: Se encontraron {len(pinterest_results)} referencias de Pinterest. "
                f"Las imágenes fueron descargadas y se usarán como referencia de estilo en la generación.]"
            )

        # Build user message content: text + optional vision blocks for reference images
        user_content: str | list[dict] = enhanced_message
        if images:
            blocks: list[dict] = [{"type": "text", "text": message}]
            for i, data_url in enumerate(images[:5]):  # cap at 5 images
                media_type, b64_data = parse_data_url(data_url)
                blocks.append(
                    {
                        "type": "text",
                        "text": f"\n\n[Imagen de referencia {i + 1} — usala como estilo visual o producto a replicar]\n",
                    }
                )
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    }
                )
            user_content = blocks

        messages: list[dict] = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": user_content})

        client = self._get_client()

        if client is None:
            # Fallback mode: No AI, just create plan directly
            plan = None
            if brand and self._should_create_plan(message):
                # Validate context first (requisitos del pipeline: marca, industria, productos con fotos)
                has_context, missing_msg = self._has_sufficient_context(brand, message, brand_dir)
                if not has_context:
                    return missing_msg or "Necesito más información para crear el plan.", None

                try:
                    plan_brand_dir = brand_dir or Path("brands") / brand.name
                    plan = self.create_plan(
                        prompt=message,
                        brand=brand,
                        brand_dir=plan_brand_dir,
                    )
                    return (
                        "Plan creado. Configure ANTHROPIC_API_KEY para conversación con AI.",
                        plan,
                    )
                except Exception as e:
                    logger.error(f"Plan creation error: {e}")
                    return f"Error al crear plan: {e}", None
            return "Modo local: Para usar chat con AI, configure ANTHROPIC_API_KEY en .env", None

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )

            response_text = response.content[0].text

            # Check if we should create a plan
            plan = None
            if brand and self._should_create_plan(message):
                # Validate we have sufficient context (requisitos del pipeline)
                has_context, missing_msg = self._has_sufficient_context(brand, message, brand_dir)
                if not has_context:
                    return missing_msg or "Necesito más información para crear el plan.", None

                # Use brand_dir if available, otherwise infer from brand name
                plan_brand_dir = brand_dir
                if not plan_brand_dir:
                    plan_brand_dir = Path("brands") / brand.name
                    if not plan_brand_dir.exists():
                        # Try alternative paths
                        for base_path in [Path(".")]:
                            potential_dir = base_path / brand.name
                            if potential_dir.exists():
                                plan_brand_dir = potential_dir
                                break

                plan = self.create_plan(
                    prompt=message,
                    brand=brand,
                    brand_dir=plan_brand_dir,
                    pinterest_results=pinterest_results,
                )

                # In BUILD mode, auto-approve if user wants to generate
                if is_build_mode and self._should_generate_content(message):
                    # Auto-approve will be handled by the API route
                    logger.info(f"BUILD mode: Plan {plan.id} will be auto-approved")

            return response_text, plan

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Error al procesar tu mensaje: {e}", None

    def _enrich_brand_context(self, brand: Brand, brand_dir: Path) -> dict:
        """Enrich brand context with additional information (products, campaigns, etc.).
        Products use brand_dir.name (slug) for path: products/{slug}/{product}/.
        """
        context = {
            "products": [],
            "campaigns": [],
            "has_logo": False,
            "has_assets": False,
        }

        # Load products: products/{brand_slug}/{product_slug}/
        brand_slug = brand_dir.name
        products_dir = Path("products") / brand_slug
        if products_dir.exists():
            for product_dir in products_dir.iterdir():
                if product_dir.is_dir():
                    product_file = product_dir / "product.json"
                    if product_file.exists():
                        try:
                            from ..models.product import Product

                            product = Product.load(product_dir)
                            has_photos = False
                            try:
                                p = product.get_main_photo(product_dir)
                                has_photos = p.exists()
                            except ValueError:
                                pass
                            context["products"].append(
                                {
                                    "name": product.name,
                                    "slug": product_dir.name,
                                    "price": product.price,
                                    "category": product.category,
                                    "has_photos": has_photos,
                                }
                            )
                        except Exception:
                            pass  # Skip invalid products

        # Load campaigns
        campaigns_dir = brand_dir / "campaigns"
        if campaigns_dir.exists():
            for campaign_dir in campaigns_dir.iterdir():
                if campaign_dir.is_dir():
                    campaign_file = campaign_dir / "campaign.json"
                    if campaign_file.exists():
                        try:
                            from ..models.campaign import Campaign

                            campaign = Campaign.load(campaign_dir)
                            context["campaigns"].append(
                                {
                                    "name": campaign.name,
                                    "description": campaign.description,
                                    "dates": campaign.dates,
                                }
                            )
                        except Exception:
                            pass  # Skip invalid campaigns

        # Check assets
        context["has_logo"] = brand.get_logo_path(brand_dir) is not None
        context["has_assets"] = any(
            [
                brand.get_asset_path(brand_dir, "logo"),
                brand.get_asset_path(brand_dir, "logo_white"),
                brand.get_asset_path(brand_dir, "icon"),
            ]
        )

        return context

    def _build_system_prompt(self, brand: Brand | None, brand_dir: Path | None = None) -> str:
        """Build system prompt for chat."""
        # Prompt principal: Experto en Marketing/CM
        marketing_expertise = """Sos un experto en marketing digital y community management con 10+ años de experiencia en campañas de redes sociales para múltiples rubros (food & beverage, retail, e-commerce, servicios, etc.).

## Tu Expertise en Marketing y Redes Sociales

**Estrategia de Contenido:**
- Planificación de calendarios editoriales
- Segmentación por audiencia y plataforma
- Timing óptimo de publicación
- Estrategias de engagement y conversión

**Copywriting para Redes:**
- Captions efectivos para Instagram (feed y stories)
- CTAs que convierten
- Hashtags estratégicos por industria
- Adaptación de tono según objetivo (promocional, informativo, engagement, branding)

**Análisis de Tendencias:**
- Tendencias visuales 2026 (autenticidad, biophilic design, warm tones)
- Formatos que funcionan (carousel, single post, stories)
- Ocasiones especiales y fechas relevantes por industria
- Competencia y benchmarking

**Mejores Prácticas por Rubro:**
- **Food & Beverage**: Lifestyle warm, appetizing visuals, horarios de comida
- **Retail/E-commerce**: Product shots claros, lifestyle context, urgency
- **Servicios**: Trust-building, before/after, testimonials visuales
- **Farmacia/Salud**: Clean, professional, informative

**Tu Rol Principal:**
1. Entender la intención del usuario (promocionar, lanzar, informar, engagement)
2. Crear estrategias de contenido efectivas
3. Sugerir copies que conviertan
4. Recomendar estilos visuales según rubro y objetivo
5. Planificar campañas con fechas y temas relevantes"""

        # Conocimiento del sistema (contexto técnico, más breve)
        system_context = """
## Contexto del Sistema CM-Agents (Referencia Técnica)

Trabajás dentro de CM-Agents, un sistema que genera imágenes de productos para redes sociales usando IA.

**Flujo del Sistema:**
1. PLAN Mode: Creás planes de contenido con items (producto, tamaño, estilo, copy)
2. BUILD Mode: El sistema ejecuta automáticamente cuando aprobás el plan
3. Pipeline: Extractor → Designer → Generator (3 agentes especializados)
4. Variantes: Podés generar múltiples variantes por item (1-10) con diferentes composiciones/iluminación

**Capacidades Técnicas (para explicar si el usuario pregunta):**
- El sistema replica el producto EXACTAMENTE usando imágenes de referencia
- El texto se integra en la imagen (no overlay posterior)
- Estilos se auto-seleccionan según marca/categoría/mood
- Costo: ~$0.05 por imagen base (multiplicado por variantes)

**Cuándo usar conocimiento técnico:**
- Solo cuando el usuario pregunta cómo funciona el sistema
- Para explicar costos o limitaciones
- Para sugerir variantes múltiples cuando tiene sentido estratégico
- NO mezcles detalles técnicos en respuestas de marketing (mantené el foco en estrategia)

## Requisitos del Pipeline de Generación (Build) — Lo que el siguiente agente NECESITA

Cuando el usuario apruebe el plan, el **GenerationPipeline** (Extractor → Designer → Generator) va a ejecutarlo. Para que no falle, cada item del plan debe tener:

1. **product** = slug de un producto que EXISTA en `products/{marca}/{product}/` con:
   - `product.json` (name, price, description; `visual_description` opcional pero mejora resultados)
   - **Al menos una foto** en `photos/` (el Generador la usa para replicar el producto de forma exacta)

2. **Referencia de estilo** (una de estas):
   - `reference_urls` (imágenes de Pinterest ya buscadas/descargadas)
   - Imágenes adjuntas del usuario
   - O que exista en `brands/{marca}/references/` o en las fotos del producto

3. **Marca** = slug del directorio en `brands/` (ej: resto-mario)

4. **Industria** en la marca (para Designer y recomendaciones de estilo)

## Preguntas que DEBES hacer ANTES de crear un plan (para que el Build no falle)

Pedile al usuario exactamente lo que el pipeline espera:

1. **Si no hay marca:**
   "¿Para qué marca es? Necesito el nombre de la marca (la carpeta en brands/)."

2. **Si falta industria en la marca:**
   "Para armar el plan bien, necesito el **tipo de negocio/industria** (ej: food_restaurant, retail, pharmacy, wine_spirits). ¿Podés completarlo en brand.json o decímelo?"

3. **Si no hay productos con fotos en products/{marca}/:**
   "Para generar las imágenes, el siguiente paso necesita **productos configurados**: cada uno en products/{marca}/&lt;producto&gt;/ con product.json y **al menos una foto en photos/** (el generador la usa para replicar el producto). ¿Tenés productos cargados? Si no, crealos ahí con esa estructura."

4. **Si no hay referencia de estilo (Pinterest, adjunto o en references/):**
   "¿Tenés una imagen de referencia de estilo (Pinterest, mockup) o querés que busque en Pinterest? Si no, hace falta al menos una en brands/{marca}/references/ o en las fotos del producto."

5. **Si hay varios productos y el usuario no aclara cuál:**
   "¿Para qué producto es? (p. ej. hamburguesa, sprite)."

**Al armar cada item del plan:** El campo **product** tiene que ser el **slug** de un producto existente en products/{marca}/ (ej: hamburguesa, sprite). **Nunca uses 'producto-general'** si hay productos cargados. Elegí el que coincida con lo que pide el usuario o uno que tenga fotos."""

        # Comportamiento y comunicación
        behavior = """
## Comportamiento y Comunicación

**Prioridad:**
- Tu expertise principal es MARKETING y ESTRATEGIA de contenido
- El conocimiento técnico es contexto secundario (usalo solo cuando sea relevante)
- Enfocate en crear planes efectivos, no en explicar cómo funciona el sistema

**Modos de Trabajo:**
- **PLAN Mode** (default): Enfocate en planificación, estrategia, copywriting, calendarios. Crear planes de contenido.
- **BUILD Mode**: El usuario quiere generar imágenes. Si menciona "genera", "aprueba", "ejecuta" → auto-aprobar y ejecutar BUILD automáticamente.

**Orquestación de Agentes (CRÍTICO - Sos el Orquestador Principal):**

Cuando el usuario pide buscar en Pinterest:
1. **Detectás** la solicitud ("busca en pinterest", "pinterest", etc.)
2. **Extraés** el query de búsqueda del mensaje
3. **Usás MCPClientService.search_pinterest(query, limit=5, download=True)**
   - El MCP descarga automáticamente las imágenes a `references/`
   - Recibís resultados con URLs y metadata
4. **Agregás** las URLs a los items del plan (`item.reference_urls`)
5. **Cuando se aprueba el plan**, el GenerationPipeline:
   - Busca las imágenes descargadas en `references/` (más recientes primero)
   - ExtractorAgent.analyze() → Analiza las referencias descargadas
   - DesignerAgent.build_prompt() → Construye prompts basados en el análisis
   - GeneratorAgent.generate_with_image_refs() → Genera imágenes finales

**Flujo Completo de Orquestación:**
```
Usuario: "busca en pinterest ideas para cyber monday"
  ↓
StrategistAgent:
  1. Detecta "pinterest" → _should_search_pinterest() = True
  2. Extrae query: "ideas para cyber monday"
  3. Llama: MCPClientService.search_pinterest("ideas para cyber monday", limit=5, download=True)
  4. MCP descarga imágenes a references/
  5. Recibe resultados con URLs
  6. Crea ContentPlan con item.reference_urls = [url1, url2, ...]
  ↓
Usuario aprueba → BUILD Mode
  ↓
GenerationPipeline.execute_generation():
  1. Lee item.reference_urls
  2. Busca archivos descargados en references/ (más recientes)
  3. ExtractorAgent.analyze(reference_path) → ReferenceAnalysis
  4. DesignerAgent.build_prompt(analysis, brand, product) → GenerationPrompt
  5. GeneratorAgent.generate_with_image_refs(prompt, [ref_path, product_path, logo]) → Imagen final
```

**IMPORTANTE - Tu Rol como Orquestador:**
- NO solo creás planes, **orquestás todo el flujo**
- Cuando detectás Pinterest, **buscás y descargás automáticamente**
- Las referencias se pasan al pipeline **automáticamente** cuando se aprueba
- Explicá al usuario qué estás haciendo: "Buscando en Pinterest...", "Encontré 5 referencias..."

**Detección Automática:**
- "variantes", "varias opciones" → Sugerir múltiples variantes (4 es buen default)
- "me gusta, ahora genera" → Auto-aprobar y ejecutar
- "crear", "generar", "hacer" → Crear plan automáticamente
- "busca en pinterest", "pinterest" → El backend ya buscó, recibís los resultados en pinterest_results
- Si el mensaje empieza con "[MODO BUILD]" → Estás en BUILD mode, prioriza ejecución sobre planificación

**Cuando recibís pinterest_results:**
- Las imágenes ya fueron descargadas por el backend usando MCP
- Agregás las URLs a los items del plan (item.reference_urls)
- Mencioná en tu respuesta: "Encontré X referencias en Pinterest que usaré como inspiración"
- El pipeline usará esas referencias automáticamente cuando se apruebe el plan

**Cuando el usuario adjunte imágenes:**
- Analizalas como experto en marketing: ¿qué transmite? ¿qué estilo tiene? ¿cómo lo usarías?
- Mencioná qué ves y cómo lo aplicarías estratégicamente
- El sistema técnico las procesará automáticamente (no necesitás explicar esto a menos que pregunten)

**Comunicación:**
- Responde SIEMPRE en español
- Sé conciso pero estratégico
- Enfocate en valor de marketing, no en detalles técnicos
- Mostrá confianza en tus recomendaciones estratégicas

**Ejemplo de Respuesta (Enfoque Marketing):**
Perfecto, para Black Friday te sugiero un enfoque de urgencia con copy que genere FOMO. El estilo lifestyle_warm funciona muy bien para food porque transmite calidez y apetito. Te propongo 4 variantes con diferentes ángulos y composiciones para que tengas opciones y puedas testear cuál convierte mejor. ¿Querés que incluya hashtags específicos de Black Friday?"""

        # Combinar prompts
        base_prompt = marketing_expertise + system_context + behavior

        if brand:
            # Enrich brand context with products, campaigns, etc.
            enriched_context = {}
            if brand_dir:
                enriched_context = self._enrich_brand_context(brand, brand_dir)

            # Build comprehensive brand context
            brand_info_parts = [
                f"Marca: {brand.name}",
                f"Industria: {brand.industry or 'No especificada'}",
            ]

            if brand.identity:
                if brand.identity.tagline:
                    brand_info_parts.append(f"Tagline: {brand.identity.tagline}")
                if brand.identity.voice:
                    brand_info_parts.append(f"Voz de marca: {', '.join(brand.identity.voice)}")
                if brand.identity.values:
                    brand_info_parts.append(f"Valores: {', '.join(brand.identity.values)}")

            if brand.palette:
                brand_info_parts.append(
                    f"Colores: Primary {brand.palette.primary}, Secondary {brand.palette.secondary}"
                )

            preferred_styles = brand.get_preferred_styles()
            if preferred_styles:
                brand_info_parts.append(
                    f"Estilos visuales preferidos: {', '.join(preferred_styles)}"
                )
            else:
                brand_info_parts.append("Estilos: auto-selección según categoría")

            avoid_styles = brand.get_avoid_styles()
            if avoid_styles:
                brand_info_parts.append(f"Evitar: {', '.join(avoid_styles)}")

            if brand.style.mood:
                brand_info_parts.append(f"Mood: {', '.join(brand.style.mood)}")

            if brand.style.photography_style:
                brand_info_parts.append(f"Estilo fotografía: {brand.style.photography_style}")

            # Add products if available (slug para que sepas el id que usa el pipeline)
            if enriched_context.get("products"):
                parts = []
                for p in enriched_context["products"]:
                    slug = p.get("slug", p.get("name", ""))
                    foto = " [con foto]" if p.get("has_photos") else " [sin foto]"
                    parts.append(f"{slug}: {p['name']} ({p['price']}){foto}")
                brand_info_parts.append("Productos disponibles: " + ", ".join(parts))

            # Add campaigns if available
            if enriched_context.get("campaigns"):
                campaigns_list = ", ".join([c["name"] for c in enriched_context["campaigns"]])
                brand_info_parts.append(f"Campañas activas: {campaigns_list}")

            brand_context = f"""

## Contexto de la Marca Actual

{chr(10).join(brand_info_parts)}

**IMPORTANTE - Reglas de Contexto:**
- Usá SOLO la información proporcionada arriba sobre la marca
- NO asumas información que no está especificada (ej: tipo de negocio, productos, industria)
- Si falta información crítica (industria, productos), preguntale al usuario antes de crear planes
- Si el usuario menciona productos o servicios que no están en la lista, confirmá primero
- Si la industria no está especificada, preguntá antes de asumir un rubro

Usá esta información para crear planes alineados con la identidad de la marca."""

            return base_prompt + brand_context

        # No brand context - add warning
        no_brand_warning = """

## ⚠️ IMPORTANTE - Sin Contexto de Marca

No se proporcionó información de marca. Antes de crear planes:

1. **Preguntá al usuario** sobre:
   - Tipo de negocio/industria (restaurante, retail, servicios, etc.)
   - Productos o servicios principales
   - Objetivo del contenido (promocionar, informar, engagement)

2. **NO asumas** información sobre:
   - Tipo de negocio (NO asumas que es una cervecería, restaurante, etc.)
   - Productos específicos
   - Estilo visual preferido

3. **Solicitá contexto** antes de generar planes detallados.

Ejemplo de respuesta cuando falta contexto:
'Para crear un plan efectivo para Black Friday, necesito saber: ¿qué tipo de negocio tenés? ¿qué productos o servicios ofrecés? Con esa información puedo diseñar una estrategia personalizada.'"""

        return base_prompt + no_brand_warning

    def _extract_requested_product_slugs(self, prompt: str, enriched: dict) -> list[str]:
        """Slugs de productos que aparecen en el prompt y existen con has_photos."""
        products = enriched.get("products", [])
        prompt_lower = prompt.lower()
        return [
            p["slug"]
            for p in products
            if p.get("has_photos")
            and (
                (p.get("slug") or "") in prompt_lower
                or ((p.get("name") or "").lower() in prompt_lower)
            )
        ]

    def _has_sufficient_context(
        self, brand: Brand | None, message: str, brand_dir: Path | None = None
    ) -> tuple[bool, str | None]:
        """Check if we have sufficient context to create a plan that the pipeline can run.
        Validates: marca, industria, productos con fotos (lo que espera el GenerationPipeline).
        Returns:
            Tuple of (has_sufficient_context, missing_info_message)
        """
        if not brand:
            return (
                False,
                "No se proporcionó información de marca. ¿Para qué marca es? (necesito el nombre de la carpeta en brands/).",
            )

        if not brand.industry:
            return (
                False,
                "Para crear un plan que el pipeline pueda ejecutar, necesito el **tipo de negocio/industria** (ej: food_restaurant, retail, pharmacy). Actualizá brand.json o indicámela.",
            )

        if not brand_dir or not brand_dir.exists():
            return (
                False,
                "No se encontró el directorio de la marca en brands/. Verificá que exista la carpeta de la marca.",
            )

        # Productos: el pipeline necesita products/{slug}/{product}/ con product.json y al menos una foto
        brand_slug = brand_dir.name
        products_dir = Path("products") / brand_slug
        if not products_dir.exists():
            return False, (
                f"Para generar imágenes, el pipeline necesita **productos** en products/{brand_slug}/ "
                "con product.json y al menos una foto en photos/. ¿Tenés productos cargados? "
                "Si no, crealos con: products/{0}/<producto>/product.json y photos/."
            ).format(brand_slug)

        subdirs = [
            d for d in products_dir.iterdir() if d.is_dir() and (d / "product.json").exists()
        ]
        if not subdirs:
            return False, (
                f"No hay productos con product.json en products/{brand_slug}/. "
                "El pipeline necesita al menos un producto con product.json y fotos en photos/."
            )

        from ..models.product import Product

        has_any_photos = False
        for d in subdirs:
            try:
                prod = Product.load(d)
                prod.get_main_photo(d)
                has_any_photos = True
                break
            except (ValueError, FileNotFoundError):
                pass
        if not has_any_photos:
            return False, (
                "Los productos necesitan **al menos una foto** (en photos/ y referenciada en product.json). "
                "El generador la usa para replicar el producto. Agregá fotos a los productos."
            )

        return True, None

    def _should_create_plan(self, message: str) -> bool:
        """Determine if we should create a plan from the message."""
        plan_keywords = [
            "crear",
            "generar",
            "hacer",
            "quiero",
            "necesito",
            "planificar",
            "programar",
            "publicar",
            "post",
            "contenido",
            "imagen",
            "diseño",
            "campaña",
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in plan_keywords)

    def _should_generate_content(self, message: str) -> bool:
        """Determine if the user wants to generate content (approve and execute plan)."""
        generate_keywords = [
            "genera",
            "generar",
            "me gusta",
            "aprobado",
            "apruebo",
            "adelante",
            "hacelo",
            "ejecuta",
            "procede",
            "vamos",
            "dale",
            "ahora genera",
            "genera el contenido",
            "genera las imágenes",
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in generate_keywords)
