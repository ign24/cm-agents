"""StrategistAgent unit tests."""

from pathlib import Path

from cm_agents.agents.strategist import KnowledgeBase, StrategistAgent
from cm_agents.models.brand import Brand


class TestKnowledgeBase:
    """KnowledgeBase tests."""

    def test_loads_design_styles(self, knowledge_dir: Path):
        """KnowledgeBase loads design styles from JSON."""
        kb = KnowledgeBase(knowledge_dir)
        styles = kb.design_styles
        assert "styles" in styles
        assert "minimal_clean" in styles["styles"]

    def test_handles_missing_files(self, tmp_path: Path):
        """KnowledgeBase handles missing files gracefully."""
        kb = KnowledgeBase(tmp_path)
        assert kb.calendar == {}
        assert kb.insights == {}
        assert kb.copy_templates == {}

    def test_get_recommended_styles_with_unknown_industry(self, knowledge_dir: Path):
        """Returns default style for unknown industry."""
        kb = KnowledgeBase(knowledge_dir)
        styles = kb.get_recommended_styles("unknown_industry")
        assert styles == ["minimal_clean"]


class TestStrategistAgent:
    """StrategistAgent tests."""

    def test_analyze_intent_detects_promocion(self, knowledge_dir: Path):
        """Detects promotional intent."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        intent = agent._analyze_intent("Quiero crear una promo 2x1", {})
        assert intent.objective == "promocionar"

    def test_analyze_intent_detects_lanzamiento(self, knowledge_dir: Path):
        """Detects launch intent."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        intent = agent._analyze_intent("Lanzar nuevo producto", {})
        assert intent.objective == "lanzamiento"

    def test_analyze_intent_detects_occasion(self, knowledge_dir: Path):
        """Detects occasion from prompt."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        intent = agent._analyze_intent("Post para el día del padre", {})
        assert intent.occasion == "dia_del_padre"

    def test_analyze_intent_detects_tone(self, knowledge_dir: Path):
        """Detects tone from prompt."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        intent = agent._analyze_intent("Contenido urgente premium", {})
        assert "urgente" in intent.tone
        assert "elegante" in intent.tone

    def test_analyze_intent_detects_constraints(self, knowledge_dir: Path):
        """Detects constraints from prompt."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        intent = agent._analyze_intent("Sin texto, solo vertical", {})
        assert "sin_texto" in intent.constraints
        assert "vertical" in intent.constraints

    def test_should_create_plan_with_action_keywords(self, knowledge_dir: Path):
        """Returns True for action keywords."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        assert agent._should_create_plan("Crear un post para Instagram") is True
        assert agent._should_create_plan("Generar contenido") is True
        assert agent._should_create_plan("Quiero una imagen") is True

    def test_should_not_create_plan_for_questions(self, knowledge_dir: Path):
        """Returns False for simple questions."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        assert agent._should_create_plan("Hola") is False
        assert agent._should_create_plan("¿Cómo estás?") is False

    def test_create_plan_returns_plan(self, brands_dir: Path, knowledge_dir: Path):
        """create_plan returns a ContentPlan."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        brand = Brand.load(brands_dir / "test-brand")

        plan = agent.create_plan(
            prompt="Crear post promocional",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
        )

        assert plan is not None
        assert plan.brand == "test-brand"
        assert len(plan.items) > 0
        assert plan.intent.objective == "promocionar"

    def test_create_plan_generates_items_for_both_sizes(
        self, brands_dir: Path, knowledge_dir: Path
    ):
        """Plan includes both feed and story items by default."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        brand = Brand.load(brands_dir / "test-brand")

        plan = agent.create_plan(
            prompt="Crear contenido",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
        )

        sizes = [item.size for item in plan.items]
        assert "feed" in sizes
        assert "story" in sizes

    def test_create_plan_respects_vertical_constraint(self, brands_dir: Path, knowledge_dir: Path):
        """Plan only includes story when vertical constraint."""
        agent = StrategistAgent(knowledge_dir=knowledge_dir)
        brand = Brand.load(brands_dir / "test-brand")

        plan = agent.create_plan(
            prompt="Crear contenido vertical para story",
            brand=brand,
            brand_dir=brands_dir / "test-brand",
        )

        sizes = [item.size for item in plan.items]
        assert "story" in sizes
        # Should only have story, not feed
        assert len(sizes) == 1
