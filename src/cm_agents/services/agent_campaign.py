"""Minimal orchestrator-workers flow for campaign planning/build from CLI.

This module intentionally stays simple and operational with low overhead.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

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
    source_mode: str = "knowledge_base"
    web_query: str | None = None
    web_sources: list[dict[str, str]] = field(default_factory=list)


@dataclass
class CampaignItem:
    day: int
    theme: str
    product: str
    size: str
    style: str
    headline: str
    subheadline: str


@dataclass
class WorkerDecision:
    name: str
    run: bool
    reason: str = ""
    params: dict[str, Any] = field(default_factory=dict)


class ResearchWorker:
    """Retrieval worker over local KB with optional LangSearch web search."""

    LANGSEARCH_ENDPOINT = "https://api.langsearch.com/v1/web-search"

    def __init__(self, knowledge_dir: Path = Path("knowledge")):
        self.kb = KnowledgeBase(knowledge_dir=knowledge_dir)
        self.langsearch_api_key = os.getenv("LANGSEARCH_API_KEY", "").strip()

    @staticmethod
    def _compact_text(text: str, limit: int = 180) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    def _build_web_query(self, brand: Brand, products: dict[str, Product], objective: str) -> str:
        product_names = [p.name for p in products.values()][:3]
        products_str = ", ".join(product_names) if product_names else "consumer product"
        industry = brand.industry or "generic"
        return (
            f"visual marketing trends for {industry} campaigns, products: {products_str}, "
            f"objective: {objective}, social media ads"
        )

    def _search_web(self, query: str) -> tuple[list[dict[str, str]], str]:
        if not self.langsearch_api_key:
            return [], "disabled_missing_api_key"

        headers = {
            "Authorization": f"Bearer {self.langsearch_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "freshness": "oneMonth",
            "summary": True,
            "count": 8,
        }

        try:
            response = httpx.post(
                self.LANGSEARCH_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()
            body = response.json()
            values = body.get("data", {}).get("webPages", {}).get("value", [])
            sources: list[dict[str, str]] = []
            for item in values[:5]:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                title = str(item.get("name") or "").strip()
                snippet = str(item.get("snippet") or "").strip()
                summary = str(item.get("summary") or "").strip()
                sources.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": self._compact_text(snippet),
                        "summary": self._compact_text(summary),
                    }
                )
            if not sources:
                return [], "no_results"
            return sources, "ok"
        except Exception:
            return [], "request_failed"

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

        web_query: str | None = None
        web_sources: list[dict[str, str]] = []
        source_mode = "knowledge_base"
        if self.langsearch_api_key:
            web_query = self._build_web_query(brand=brand, products=products, objective=objective)
            web_sources, web_status = self._search_web(web_query)
            if web_status == "ok" and web_sources:
                source_mode = "langsearch+knowledge_base"
                for source in web_sources[:3]:
                    source_text = (
                        source.get("summary") or source.get("snippet") or source.get("title", "")
                    )
                    if source_text:
                        key_insights.append(
                            f"Web trend: {source_text} (source: {source.get('url', '')})"
                        )
            else:
                source_mode = f"knowledge_base_fallback({web_status})"

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
            source_mode=source_mode,
            web_query=web_query,
            web_sources=web_sources,
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
        ref_files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            ref_files.extend(refs_dir.glob(ext))
        return len(ref_files) > 0

    @staticmethod
    def _infer_include_text(objective: str) -> bool:
        msg = (objective or "").strip().lower()
        no_text_markers = (
            "sin texto",
            "no text",
            "sin copy",
            "sin headline",
            "sin titulares",
            "solo producto",
            "solo la foto",
            "sin tipografia",
            "sin tipografía",
        )
        return not any(m in msg for m in no_text_markers)

    def _policy_worker_plan(
        self,
        *,
        build: bool,
        include_text: bool,
        has_style_ref_input: bool,
        has_brand_style_ref: bool,
        objective: str,
        max_retries: int,
    ) -> list[WorkerDecision]:
        """Deterministic fallback policy when LLM orchestration is unavailable."""

        obj = (objective or "").lower()
        asks_trends = any(
            k in obj
            for k in (
                "tendencia",
                "trends",
                "inspiracion",
                "inspiración",
                "que esta funcionando",
                "qué está funcionando",
                "referencias",
            )
        )

        # Research adds most value when we're missing references or user explicitly asks.
        research_run = (
            build and not has_style_ref_input and not has_brand_style_ref
        ) or asks_trends

        # Copy only matters if we allow text in the image.
        copy_run = include_text

        # Design improves coherence; keep it on for build.
        design_run = build

        generate_run = build
        qa_run = build and max_retries > 0

        return [
            WorkerDecision(
                name="research",
                run=research_run,
                reason="missing style references"
                if (research_run and not asks_trends)
                else "trend request"
                if research_run
                else "",
            ),
            WorkerDecision(
                name="copy",
                run=copy_run,
                reason="include_text=true" if copy_run else "include_text=false",
            ),
            WorkerDecision(
                name="design",
                run=design_run,
                reason="build=true" if design_run else "build=false",
            ),
            WorkerDecision(
                name="generate",
                run=generate_run,
                reason="build=true" if generate_run else "build=false",
            ),
            WorkerDecision(
                name="qa",
                run=qa_run,
                reason="max_retries>0" if qa_run else "max_retries=0 or build=false",
                params={"max_retries": max_retries},
            ),
        ]

    def _decide_worker_plan(
        self,
        *,
        brand_slug: str,
        product_slugs: list[str],
        objective: str,
        days: int,
        build: bool,
        include_text: bool,
        max_retries: int,
        has_style_ref_input: bool,
        has_brand_style_ref: bool,
    ) -> tuple[list[WorkerDecision], str, str]:
        """Return worker decisions (run/skip) with reasons.

        - If Strategist LLM is available: use it as orchestrator.
        - Else: fall back to deterministic policy.
        """

        allowed = {"research", "copy", "design", "generate", "qa"}

        client = self.strategist._get_client()
        if client is None:
            return (
                self._policy_worker_plan(
                    build=build,
                    include_text=include_text,
                    has_style_ref_input=has_style_ref_input,
                    has_brand_style_ref=has_brand_style_ref,
                    objective=objective,
                    max_retries=max_retries,
                ),
                "fallback_policy_no_llm",
                "fallback",
            )

        user_prompt = (
            "Decide which workers to run for this campaign request. Return ONLY strict JSON.\n"
            "Hard constraints:\n"
            "- If build=false: generate=false and qa=false\n"
            "- If include_text=false: copy=false\n"
            "- If build=true: generate must be true\n"
            "Policy guidance:\n"
            "- Run research if user asks for trends/inspiration OR if there is no style ref input and no brand references\n"
            "- Run copy only if include_text=true\n"
            "- Run design if build=true\n"
            "- Run qa if build=true and max_retries>0\n\n"
            f"brand={brand_slug}\n"
            f"products={product_slugs}\n"
            f"objective={objective}\n"
            f"days={days}\n"
            f"build={build}\n"
            f"include_text={include_text}\n"
            f"max_retries={max_retries}\n"
            f"has_style_ref_input={has_style_ref_input}\n"
            f"has_brand_style_ref={has_brand_style_ref}\n"
            f"allowed_workers={sorted(allowed)}\n"
            'JSON schema: {"workers": [{"name":"research","run":true,"reason":"...","params":{}}], "reason":"..."}'
        )

        try:
            response = client.messages.create(
                model=self.strategist.model,
                max_tokens=450,
                temperature=0,
                system="You are a strict JSON planner for agent orchestration. No markdown.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = self._extract_response_text(response)
            if not text:
                return (
                    self._policy_worker_plan(
                        build=build,
                        include_text=include_text,
                        has_style_ref_input=has_style_ref_input,
                        has_brand_style_ref=has_brand_style_ref,
                        objective=objective,
                        max_retries=max_retries,
                    ),
                    "fallback_empty_response",
                    "fallback",
                )

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", text)
                if not match:
                    return (
                        self._policy_worker_plan(
                            build=build,
                            include_text=include_text,
                            has_style_ref_input=has_style_ref_input,
                            has_brand_style_ref=has_brand_style_ref,
                            objective=objective,
                            max_retries=max_retries,
                        ),
                        "fallback_invalid_json",
                        "fallback",
                    )
                parsed = json.loads(match.group())

            raw_workers = parsed.get("workers", [])
            decisions_by_name: dict[str, WorkerDecision] = {
                w.name: w
                for w in self._policy_worker_plan(
                    build=build,
                    include_text=include_text,
                    has_style_ref_input=has_style_ref_input,
                    has_brand_style_ref=has_brand_style_ref,
                    objective=objective,
                    max_retries=max_retries,
                )
            }

            if isinstance(raw_workers, list):
                for w in raw_workers:
                    if not isinstance(w, dict):
                        continue
                    name = w.get("name")
                    if not isinstance(name, str) or name not in allowed:
                        continue
                    run_flag = bool(w.get("run"))
                    reason = str(w.get("reason") or "").strip()
                    raw_params = w.get("params")
                    params: dict[str, Any] = (
                        dict(raw_params) if isinstance(raw_params, dict) else {}
                    )
                    decisions_by_name[name] = WorkerDecision(
                        name=name,
                        run=run_flag,
                        reason=reason,
                        params=params,
                    )

            # Enforce hard constraints.
            if not build:
                decisions_by_name["generate"].run = False
                decisions_by_name["qa"].run = False
            if build:
                decisions_by_name["generate"].run = True
            if not include_text:
                decisions_by_name["copy"].run = False
            if max_retries <= 0:
                decisions_by_name["qa"].run = False

            # Stable ordering
            ordered = [
                decisions_by_name[n]
                for n in ("research", "copy", "design", "generate", "qa")
                if n in decisions_by_name
            ]
            return ordered, str(parsed.get("reason") or "llm_worker_plan"), "llm"
        except Exception:
            return (
                self._policy_worker_plan(
                    build=build,
                    include_text=include_text,
                    has_style_ref_input=has_style_ref_input,
                    has_brand_style_ref=has_brand_style_ref,
                    objective=objective,
                    max_retries=max_retries,
                ),
                "fallback_error",
                "fallback",
            )

    def _decide_execution_plan(
        self,
        brand_slug: str,
        product_slugs: list[str],
        objective: str,
        days: int,
        build: bool,
        has_style_ref_input: bool,
        has_brand_style_ref: bool,
        include_text: bool,
        max_retries: int,
    ) -> tuple[list[str], str, list[WorkerDecision], str]:
        """Backward-compatible wrapper returning both sequence and full decisions."""

        decisions, reason, mode = self._decide_worker_plan(
            brand_slug=brand_slug,
            product_slugs=product_slugs,
            objective=objective,
            days=days,
            build=build,
            include_text=include_text,
            max_retries=max_retries,
            has_style_ref_input=has_style_ref_input,
            has_brand_style_ref=has_brand_style_ref,
        )
        seq = [d.name for d in decisions if d.run]
        return seq, reason, decisions, mode

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
            "include_text": self._infer_include_text(user_request),
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
            "- include_text is boolean (false if user asks for no text/copy)\n"
            "- products must be subset of available_products (or empty for auto)\n"
            'JSON schema: {"objective": "...", "days": 3, "build": true, "include_text": true, "products": ["slug"], "reason": "..."}'
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

            include_text = bool(parsed.get("include_text", default["include_text"]))

            products = [
                p
                for p in parsed.get("products", [])
                if isinstance(p, str) and p in available_products
            ]

            return {
                "objective": objective,
                "days": days,
                "build": build,
                "include_text": include_text,
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
            include_text=translation.get("include_text", True),
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
        include_text: bool | None = None,
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

        effective_include_text = (
            include_text if include_text is not None else self._infer_include_text(objective)
        )

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

        worker_sequence, worker_reason, worker_decisions, orchestrator_mode = (
            self._decide_execution_plan(
                brand_slug=brand_slug,
                product_slugs=product_slugs,
                objective=objective,
                days=days,
                build=build,
                has_style_ref_input=style_ref is not None,
                has_brand_style_ref=self._has_brand_style_reference(brand_dir),
                include_text=effective_include_text,
                max_retries=max_retries,
            )
        )

        decisions_by_name = {d.name: d for d in worker_decisions}

        orchestration_trace: list[dict[str, Any]] = [
            {
                "step": "orchestration_decision",
                "worker_sequence": worker_sequence,
                "reason": worker_reason,
                "include_text": effective_include_text,
            }
        ]

        trend = TrendBrief(
            industry=brand.industry or "generic",
            recommended_styles=brand.get_preferred_styles() or ["minimal_clean"],
            key_insights=[f"Objective focus: {objective}"],
            category_guidelines={},
        )
        if decisions_by_name.get("research", WorkerDecision("research", False)).run:
            trend = self.research.run(brand=brand, products=products, objective=objective)
            orchestration_trace.append(
                {
                    "step": "worker_done",
                    "worker": "research",
                    "source_mode": trend.source_mode,
                    "web_sources": len(trend.web_sources),
                }
            )

        def _items_without_copy() -> list[CampaignItem]:
            items: list[CampaignItem] = []
            theme_cycle = CopyWorker.THEMES
            for day_idx in range(1, days + 1):
                theme = theme_cycle[(day_idx - 1) % len(theme_cycle)]
                for product_slug in products.keys():
                    items.append(
                        CampaignItem(
                            day=day_idx,
                            theme=theme,
                            product=product_slug,
                            size="feed",
                            style="",
                            headline="",
                            subheadline="",
                        )
                    )
            return items

        if decisions_by_name.get("copy", WorkerDecision("copy", False)).run:
            copy_items = self.copy.run(products=products, days=days, objective=objective)
            orchestration_trace.append({"step": "worker_done", "worker": "copy"})
        else:
            copy_items = _items_without_copy()
            orchestration_trace.append(
                {"step": "worker_skipped", "worker": "copy", "reason": "plan"}
            )

        if decisions_by_name.get("design", WorkerDecision("design", False)).run:
            selected_style, visual_direction, designed_items = self.design.run(trend, copy_items)
            orchestration_trace.append({"step": "worker_done", "worker": "design"})
        else:
            selected_style = (brand.get_preferred_styles() or ["minimal_clean"])[0]
            visual_direction = build_visual_direction_from_style(selected_style)
            designed_items = [
                CampaignItem(**{**asdict(i), "style": selected_style}) for i in copy_items
            ]
            orchestration_trace.append(
                {"step": "worker_skipped", "worker": "design", "reason": "plan"}
            )

        generation_results: list[dict[str, Any]] = []
        qa_enabled = decisions_by_name.get("qa", WorkerDecision("qa", False)).run
        generate_enabled = decisions_by_name.get("generate", WorkerDecision("generate", False)).run

        if build and generate_enabled:
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

                if product_ref is not None and not Path(product_ref).exists():
                    generation_results.append(
                        {
                            "item": asdict(item),
                            "error": f"Referencia de producto no encontrada: {product_ref}",
                        }
                    )
                    continue

                item_done = False
                last_error: str | None = None
                attempts = 0
                max_attempts = max(1, max_retries + 1) if qa_enabled else 1

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
                            include_text=effective_include_text,
                            product_ref_path=product_ref if product_ref else None,
                            campaign_dir=None,
                            headline=item.headline,
                            subheadline=item.subheadline,
                            theme=item.theme,
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
                "include_text": effective_include_text,
                "max_retries": max_retries,
            },
            "worker_plan": {
                "sequence": worker_sequence,
                "reason": worker_reason,
                "mode": orchestrator_mode,
                "workers": [asdict(w) for w in worker_decisions],
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
                    photo_path = product.get_main_photo(product_dir)
                    if not Path(photo_path).exists():
                        continue
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
            ref_files = []
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
                ref_files.extend(refs_dir.glob(ext))
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
            f"- Research source mode: {trend.get('source_mode', 'knowledge_base')}",
            f"- Web sources: {len(trend.get('web_sources', []))}",
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
