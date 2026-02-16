"""Minimal orchestrator-workers flow for campaign planning/build from CLI.

This module intentionally stays simple and operational with low overhead.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..agents.strategist import KnowledgeBase, StrategistAgent
from ..models.brand import Brand
from ..models.product import Product
from ..pipeline import GenerationPipeline
from ..styles import build_visual_direction_from_style


@dataclass
class TrendBrief:
    industry: str
    recommended_styles: list[str]
    key_insights: list[str]
    category_guidelines: dict[str, dict[str, Any]]


@dataclass
class CampaignItem:
    day: int
    theme: str
    product: str
    size: str
    style: str
    headline: str
    subheadline: str


class ResearchWorker:
    """Local Agentic-RAG-like retrieval over knowledge files."""

    def __init__(self, knowledge_dir: Path = Path("knowledge")):
        self.kb = KnowledgeBase(knowledge_dir=knowledge_dir)

    def run(self, brand: Brand, products: dict[str, Product], objective: str) -> TrendBrief:
        industry = brand.industry or "generic"
        industry_info = self.kb.get_industry_info(industry)

        preferred = brand.get_preferred_styles()
        recommended = preferred or self.kb.get_recommended_styles(industry)
        if not recommended:
            recommended = ["minimal_clean"]

        key_insights: list[str] = []
        if industry_info:
            for insight in industry_info.get("visual_trends", [])[:3]:
                key_insights.append(str(insight))
            for insight in industry_info.get("best_practices", [])[:2]:
                key_insights.append(str(insight))

        if not key_insights:
            key_insights = [
                f"Objective focus: {objective}",
                "Keep product fidelity and clear hierarchy.",
                "Prefer high contrast text areas for social formats.",
            ]

        category_guidelines: dict[str, dict[str, Any]] = {}
        for slug, product in products.items():
            category = product.category or "generic"
            if category not in category_guidelines:
                category_guidelines[category] = self.kb.get_category_guidelines(category)

        return TrendBrief(
            industry=industry,
            recommended_styles=list(dict.fromkeys(recommended)),
            key_insights=key_insights,
            category_guidelines=category_guidelines,
        )


class CopyWorker:
    """Simple deterministic copy generator."""

    THEMES = ["teaser", "main_offer", "last_chance", "social_proof", "reminder"]

    def run(self, products: dict[str, Product], days: int, objective: str) -> list[CampaignItem]:
        items: list[CampaignItem] = []
        for day in range(1, days + 1):
            theme = self.THEMES[(day - 1) % len(self.THEMES)]
            for product_slug, product in products.items():
                base = product.name
                if theme == "teaser":
                    headline = f"{base} que se siente distinto"
                    subheadline = "Pronto una propuesta visual nueva"
                elif theme == "main_offer":
                    headline = f"{base} protagonista del dia"
                    subheadline = f"Campana enfocada en {objective}"
                elif theme == "last_chance":
                    headline = f"Ultimo impulso para {base}"
                    subheadline = "Cierre de campana con alta recordacion"
                elif theme == "social_proof":
                    headline = f"{base} recomendado por la comunidad"
                    subheadline = "Confianza, consistencia y resultados"
                else:
                    headline = f"{base} sigue en tendencia"
                    subheadline = "No cortes el momentum de la campana"

                items.append(
                    CampaignItem(
                        day=day,
                        theme=theme,
                        product=product_slug,
                        size="feed",
                        style="",
                        headline=headline,
                        subheadline=subheadline,
                    )
                )
        return items


class DesignWorker:
    """Applies style decisions and visual direction."""

    def run(
        self, trend: TrendBrief, items: list[CampaignItem]
    ) -> tuple[str, str, list[CampaignItem]]:
        selected_style = (
            trend.recommended_styles[0] if trend.recommended_styles else "minimal_clean"
        )
        visual_direction = build_visual_direction_from_style(selected_style)

        for item in items:
            item.style = selected_style

        return selected_style, visual_direction, items


class QACriticWorker:
    """Very small QA gate to keep loop bounded and observable."""

    def run(self, image_path: Path | None, error: str | None = None) -> dict[str, Any]:
        if error:
            return {
                "ok": False,
                "reason": "generation_error",
                "details": error,
            }

        if image_path is None or not image_path.exists():
            return {
                "ok": False,
                "reason": "missing_file",
                "details": "Image file not found after generation.",
            }

        # Very lightweight heuristic: file should not be tiny/corrupted
        size_bytes = image_path.stat().st_size
        if size_bytes < 20_000:
            return {
                "ok": False,
                "reason": "suspicious_small_image",
                "details": f"Generated file too small ({size_bytes} bytes).",
            }

        return {
            "ok": True,
            "reason": "passed",
            "details": f"Image looks valid ({size_bytes} bytes).",
        }


class OrchestratorCampaignService:
    """Lead orchestrator that coordinates specialist workers."""

    def __init__(self, knowledge_dir: Path = Path("knowledge")):
        self.research = ResearchWorker(knowledge_dir=knowledge_dir)
        self.copy = CopyWorker()
        self.design = DesignWorker()
        self.qa = QACriticWorker()
        self.strategist = StrategistAgent(knowledge_dir=knowledge_dir)

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """Extract text safely from Anthropic response blocks."""
        parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _has_brand_style_reference(brand_dir: Path) -> bool:
        refs_dir = brand_dir / "references"
        if not refs_dir.exists():
            return False
        ref_files = list(refs_dir.glob("*.jpg")) + list(refs_dir.glob("*.png"))
        return len(ref_files) > 0

    def _decide_execution_plan(
        self,
        brand_slug: str,
        product_slugs: list[str],
        objective: str,
        days: int,
        build: bool,
        has_style_ref_input: bool,
        has_brand_style_ref: bool,
    ) -> tuple[list[str], str]:
        """Ask Strategist LLM when to execute each worker; fallback to safe default."""
        default_sequence = ["research", "copy", "design"] + (["generate", "qa"] if build else [])

        client = self.strategist._get_client()
        if client is None:
            return default_sequence, "fallback_local_no_llm"

        allowed = ["research", "copy", "design", "generate", "qa"]
        try:
            user_prompt = (
                "Decide CUANDO ejecutar cada worker para esta campana y responde SOLO JSON.\n"
                f"brand={brand_slug}\n"
                f"products={product_slugs}\n"
                f"objective={objective}\n"
                f"days={days}\n"
                f"build={build}\n"
                f"has_style_ref_input={has_style_ref_input}\n"
                f"has_brand_style_ref={has_brand_style_ref}\n"
                f"allowed_workers={allowed}\n"
                "Rules:\n"
                "- If build=false, generate and qa MUST be false.\n"
                "- If build=true, generate MUST be true.\n"
                "- If generate=true, qa SHOULD be true.\n"
                "- copy and design SHOULD usually run for campaign quality.\n"
                'JSON schema: {"workers": [{"name":"research","run":true,"when":"..."}], "reason": "..."}'
            )

            response = client.messages.create(
                model=self.strategist.model,
                max_tokens=300,
                temperature=0,
                system=(
                    "You are an orchestration planner for AI campaign pipelines. "
                    "Decide exactly when each worker should execute based on context. "
                    "Return strict JSON only. "
                    "No markdown, no prose."
                ),
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = self._extract_response_text(response)
            if not text:
                return default_sequence, "fallback_empty_response"
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", text)
                if not match:
                    return default_sequence, "fallback_invalid_json"
                parsed = json.loads(match.group())

            workers_raw = parsed.get("workers", [])
            seq_raw = [w.get("name") for w in workers_raw if isinstance(w, dict) and w.get("run")]
            seq: list[str] = []
            for w in seq_raw:
                if isinstance(w, str) and w in allowed and w not in seq:
                    seq.append(w)

            # Hard constraints
            if "copy" not in seq:
                seq.insert(0, "copy")
            if "design" not in seq:
                seq.append("design")
            if build and "generate" not in seq:
                seq.append("generate")
            if build and "qa" not in seq:
                seq.append("qa")
            if not build:
                seq = [w for w in seq if w not in {"generate", "qa"}]

            return seq, str(parsed.get("reason", "llm_execution_plan"))
        except Exception:
            return default_sequence, "fallback_error"

    def _translate_user_request(
        self,
        brand_slug: str,
        user_request: str,
        available_products: list[str],
        require_llm_orchestrator: bool,
    ) -> dict[str, Any]:
        """Translate dynamic user input into orchestrator params using Strategist LLM."""
        default = {
            "objective": user_request.strip()
            or "promocionar campaña visual con consistencia de marca",
            "days": 3,
            "build": True,
            "products": [],
            "reason": "fallback_heuristic",
            "mode": "fallback",
        }

        client = self.strategist._get_client()
        if client is None:
            if require_llm_orchestrator:
                raise RuntimeError(
                    "LLM orchestrator requerido pero ANTHROPIC_API_KEY no está configurada."
                )
            return default

        prompt = (
            "Convert the user request into execution params for campaign workers. Return ONLY strict JSON.\n"
            f"brand={brand_slug}\n"
            f"available_products={available_products}\n"
            f"user_request={user_request}\n"
            "Rules:\n"
            "- days must be integer between 1 and 14\n"
            "- build is boolean\n"
            "- products must be subset of available_products (or empty for auto)\n"
            'JSON schema: {"objective": "...", "days": 3, "build": true, "products": ["slug"], "reason": "..."}'
        )

        try:
            response = client.messages.create(
                model=self.strategist.model,
                max_tokens=300,
                temperature=0,
                system="You are a strict JSON translator for agent orchestration parameters.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = self._extract_response_text(response)
            if not text:
                if require_llm_orchestrator:
                    raise RuntimeError(
                        "Strategist devolvió respuesta vacía para traducción de input"
                    )
                return default

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", text)
                if not match:
                    if require_llm_orchestrator:
                        raise RuntimeError("Strategist devolvió JSON inválido para traducción")
                    return default
                parsed = json.loads(match.group())

            objective = str(parsed.get("objective") or default["objective"]).strip()
            try:
                days = int(parsed.get("days", default["days"]))
            except Exception:
                days = 3
            days = max(1, min(14, days))

            build = bool(parsed.get("build", True))

            products = [
                p
                for p in parsed.get("products", [])
                if isinstance(p, str) and p in available_products
            ]

            return {
                "objective": objective,
                "days": days,
                "build": build,
                "products": products,
                "reason": str(parsed.get("reason", "llm_translated")),
                "mode": "llm",
            }
        except Exception:
            if require_llm_orchestrator:
                raise
            return default

    def run_from_user_input(
        self,
        brand_slug: str,
        user_request: str,
        style_ref: Path | None = None,
        max_retries: int = 1,
        require_llm_orchestrator: bool = True,
    ) -> dict[str, Any]:
        """Dynamic entrypoint: Strategist translates user input, then orchestrates workers."""
        available_products = self._discover_products_with_photos(brand_slug)
        translation = self._translate_user_request(
            brand_slug=brand_slug,
            user_request=user_request,
            available_products=available_products,
            require_llm_orchestrator=require_llm_orchestrator,
        )

        result = self.run(
            brand_slug=brand_slug,
            product_slugs=translation["products"] or None,
            objective=translation["objective"],
            days=translation["days"],
            build=translation["build"],
            style_ref=style_ref,
            max_retries=max_retries,
            require_llm_orchestrator=require_llm_orchestrator,
        )

        artifacts = result["artifacts"]
        artifacts["input_translation"] = translation
        with open(result["run_dir"] / "artifacts.json", "w", encoding="utf-8") as f:
            json.dump(artifacts, f, indent=2, ensure_ascii=False)
        result["artifacts"] = artifacts
        return result

    def run(
        self,
        brand_slug: str,
        product_slugs: list[str] | None,
        objective: str,
        days: int = 3,
        build: bool = False,
        style_ref: Path | None = None,
        max_retries: int = 1,
        require_llm_orchestrator: bool = False,
    ) -> dict[str, Any]:
        run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        run_dir = Path("outputs") / "agent_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        brand_dir = Path("brands") / brand_slug
        if not brand_dir.exists():
            raise FileNotFoundError(f"Marca no encontrada: {brand_slug}")

        brand = Brand.load(brand_dir)

        if not product_slugs:
            product_slugs = self._discover_products_with_photos(brand_slug)
            if not product_slugs:
                raise FileNotFoundError(
                    f"No hay productos con fotos en brands/{brand_slug}/products/ ni products/{brand_slug}/. "
                    "Crea al menos brands/<marca>/products/<producto>/photos/<foto>.png"
                )

        products: dict[str, Product] = {}
        for slug in product_slugs:
            product_dir = self._find_product_dir(brand_slug, slug)
            if not product_dir:
                raise FileNotFoundError(
                    f"Producto no encontrado: brands/{brand_slug}/products/{slug} (ni ruta legacy products/{brand_slug}/{slug})"
                )
            products[slug] = Product.load(product_dir)

        if require_llm_orchestrator and self.strategist._get_client() is None:
            raise RuntimeError(
                "LLM orchestrator requerido pero ANTHROPIC_API_KEY no está configurada."
            )

        worker_sequence, worker_reason = self._decide_execution_plan(
            brand_slug=brand_slug,
            product_slugs=product_slugs,
            objective=objective,
            days=days,
            build=build,
            has_style_ref_input=style_ref is not None,
            has_brand_style_ref=self._has_brand_style_reference(brand_dir),
        )
        orchestrator_mode = "llm" if not worker_reason.startswith("fallback") else "fallback"

        orchestration_trace: list[dict[str, Any]] = [
            {
                "step": "orchestration_decision",
                "worker_sequence": worker_sequence,
                "reason": worker_reason,
            }
        ]

        trend = TrendBrief(
            industry=brand.industry or "generic",
            recommended_styles=brand.get_preferred_styles() or ["minimal_clean"],
            key_insights=[f"Objective focus: {objective}"],
            category_guidelines={},
        )
        if "research" in worker_sequence:
            trend = self.research.run(brand=brand, products=products, objective=objective)
            orchestration_trace.append({"step": "worker_done", "worker": "research"})

        copy_items = self.copy.run(products=products, days=days, objective=objective)
        if "copy" in worker_sequence:
            orchestration_trace.append({"step": "worker_done", "worker": "copy"})

        selected_style, visual_direction, designed_items = self.design.run(trend, copy_items)
        if "design" in worker_sequence:
            orchestration_trace.append({"step": "worker_done", "worker": "design"})

        generation_results: list[dict[str, Any]] = []
        qa_enabled = "qa" in worker_sequence
        if build and "generate" in worker_sequence:
            pipeline = GenerationPipeline(
                generator_model="gpt-image-1.5", design_style=selected_style
            )
            reference_path = self._resolve_style_reference(style_ref, brand_dir)

            for item in designed_items:
                product_dir = self._find_product_dir(brand_slug, item.product)
                if not product_dir:
                    generation_results.append(
                        {
                            "item": asdict(item),
                            "error": f"Producto no encontrado para build: {item.product}",
                        }
                    )
                    continue
                product_obj = products[item.product]
                product_ref = None
                try:
                    product_ref = product_obj.get_main_photo(product_dir)
                except Exception:
                    product_ref = None

                item_done = False
                last_error: str | None = None
                attempts = 0
                max_attempts = max(1, max_retries + 1)

                while attempts < max_attempts and not item_done:
                    attempts += 1
                    orchestration_trace.append(
                        {
                            "step": "generate_item",
                            "item": asdict(item),
                            "attempt": attempts,
                        }
                    )
                    try:
                        results = pipeline.run(
                            reference_path=reference_path,
                            brand_dir=brand_dir,
                            product_dir=product_dir,
                            target_sizes=[item.size],
                            include_text=True,
                            product_ref_path=Path(product_ref) if product_ref else None,
                            campaign_dir=None,
                        )

                        first_image = results[0].image_path if results else None
                        qa = {"ok": True, "reason": "skipped", "details": "QA disabled by plan."}
                        if qa_enabled:
                            qa = self.qa.run(first_image)
                            orchestration_trace.append(
                                {
                                    "step": "qa_check",
                                    "item": asdict(item),
                                    "attempt": attempts,
                                    "qa": qa,
                                }
                            )

                        if qa["ok"]:
                            generation_results.extend(
                                [
                                    {
                                        "item": asdict(item),
                                        "image_path": str(r.image_path),
                                        "cost_usd": r.cost_usd,
                                        "attempt": attempts,
                                        "qa": qa,
                                    }
                                    for r in results
                                ]
                            )
                            item_done = True
                        else:
                            last_error = f"QA failed: {qa['reason']}"
                    except Exception as e:
                        last_error = str(e)
                        if qa_enabled:
                            qa = self.qa.run(None, error=last_error)
                            orchestration_trace.append(
                                {
                                    "step": "qa_check",
                                    "item": asdict(item),
                                    "attempt": attempts,
                                    "qa": qa,
                                }
                            )

                if not item_done:
                    generation_results.append(
                        {
                            "item": asdict(item),
                            "error": last_error or "unknown_error",
                            "attempts": attempts,
                        }
                    )

        artifacts = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "input": {
                "brand": brand_slug,
                "products": product_slugs,
                "objective": objective,
                "days": days,
                "build": build,
                "max_retries": max_retries,
            },
            "worker_plan": {
                "sequence": worker_sequence,
                "reason": worker_reason,
                "mode": orchestrator_mode,
            },
            "trend_brief": asdict(trend),
            "selected_style": selected_style,
            "visual_direction": visual_direction,
            "campaign_items": [asdict(i) for i in designed_items],
            "orchestration_trace": orchestration_trace,
            "generation": generation_results,
        }

        with open(run_dir / "artifacts.json", "w", encoding="utf-8") as f:
            json.dump(artifacts, f, indent=2, ensure_ascii=False)

        self._write_report(run_dir, artifacts)
        return {"run_id": run_id, "run_dir": run_dir, "artifacts": artifacts}

    @staticmethod
    def _discover_products_with_photos(brand_slug: str) -> list[str]:
        roots = [Path("brands") / brand_slug / "products", Path("products") / brand_slug]
        discovered: list[str] = []
        for products_dir in roots:
            if not products_dir.exists():
                continue
            for product_dir in products_dir.iterdir():
                if not product_dir.is_dir():
                    continue
                try:
                    product = Product.load(product_dir)
                    product.get_main_photo(product_dir)
                    if product_dir.name not in discovered:
                        discovered.append(product_dir.name)
                except Exception:
                    continue

        return discovered

    @staticmethod
    def _find_product_dir(brand_slug: str, product_slug: str) -> Path | None:
        candidates = [
            Path("brands") / brand_slug / "products" / product_slug,
            Path("products") / brand_slug / product_slug,
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    @staticmethod
    def _resolve_style_reference(style_ref: Path | None, brand_dir: Path) -> Path:
        if style_ref and style_ref.exists():
            return style_ref

        refs_dir = brand_dir / "references"
        if refs_dir.exists():
            ref_files = list(refs_dir.glob("*.jpg")) + list(refs_dir.glob("*.png"))
            if ref_files:
                return ref_files[0]

        raise FileNotFoundError(
            "No se encontro style reference. Pasar --style-ref o agregar imagen en brands/<marca>/references/."
        )

    @staticmethod
    def _write_report(run_dir: Path, artifacts: dict[str, Any]) -> None:
        trend = artifacts.get("trend_brief", {})
        report = [
            f"# Agent Campaign Run {artifacts['run_id']}",
            "",
            f"- Brand: {artifacts['input']['brand']}",
            f"- Products: {', '.join(artifacts['input']['products'])}",
            f"- Objective: {artifacts['input']['objective']}",
            f"- Days: {artifacts['input']['days']}",
            f"- Build executed: {artifacts['input']['build']}",
            "",
            "## Trend Brief",
            f"- Industry: {trend.get('industry', '-')}",
            f"- Selected style: {artifacts.get('selected_style', '-')}",
            "",
            "## Items",
            f"- Total items: {len(artifacts.get('campaign_items', []))}",
            f"- Generated outputs: {len([g for g in artifacts.get('generation', []) if 'image_path' in g])}",
            f"- Errors: {len([g for g in artifacts.get('generation', []) if 'error' in g])}",
            "",
            "Artifacts:",
            "- artifacts.json",
        ]

        with open(run_dir / "report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(report) + "\n")
