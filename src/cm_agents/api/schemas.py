"""API schemas for request/response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Chat Schemas
# =============================================================================


class ChatMessage(BaseModel):
    """Single chat message."""

    role: Literal["user", "assistant", "system"]
    content: str
    images: list[str] = Field(default_factory=list)  # Base64 or URLs
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str
    images: list[str] = Field(default_factory=list)
    brand: str | None = None
    campaign: str | None = None


class ChatResponse(BaseModel):
    """Response from chat."""

    message: ChatMessage
    plan: "ContentPlanResponse | None" = None


# =============================================================================
# Plan Schemas
# =============================================================================


class ContentIntentResponse(BaseModel):
    """What the user wants to achieve."""

    objective: str
    product: str | None = None
    occasion: str | None = None
    tone: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class VariantResultResponse(BaseModel):
    """Result of a single variant generation."""

    variant_number: int
    output_path: str
    cost_usd: float = 0.0
    status: Literal["generated", "failed"]
    error: str | None = None
    variation_type: str | None = None


class ContentPlanItemResponse(BaseModel):
    """Single item in a content plan."""

    id: str
    product: str
    size: Literal["feed", "story"]
    style: str
    copy_suggestion: str
    reference_query: str
    reference_urls: list[str] = Field(default_factory=list)
    variants_count: int = Field(default=1, ge=1, le=10)
    status: Literal["draft", "approved", "generating", "partially_generated", "generated", "failed"]
    variants: list[VariantResultResponse] = Field(default_factory=list)
    output_path: str | None = None  # Legacy: first variant path


class ContentPlanResponse(BaseModel):
    """Full content plan response."""

    id: str
    brand: str
    intent: ContentIntentResponse
    items: list[ContentPlanItemResponse]
    created_at: datetime
    approved_at: datetime | None = None
    estimated_cost: float


class PlanCreateRequest(BaseModel):
    """Request to create a plan from natural language."""

    prompt: str
    brand: str
    campaign: str | None = None


class PlanApproveRequest(BaseModel):
    """Request to approve specific items in a plan."""

    item_ids: list[str] = Field(default_factory=list)  # Empty = approve all


# =============================================================================
# Brand Schemas
# =============================================================================


class BrandSummary(BaseModel):
    """Brief brand info for listings."""

    name: str
    slug: str
    industry: str | None = None
    logo_url: str | None = None
    campaigns_count: int = 0


class BrandListResponse(BaseModel):
    """List of brands."""

    brands: list[BrandSummary]
    total: int


# =============================================================================
# Campaign Schemas
# =============================================================================


class CampaignSummary(BaseModel):
    """Brief campaign info for listings."""

    name: str
    slug: str
    brand: str
    start_date: str
    end_date: str
    is_active: bool
    progress: tuple[int, int]  # (completed, total)


class CampaignListResponse(BaseModel):
    """List of campaigns."""

    campaigns: list[CampaignSummary]
    total: int


# =============================================================================
# Generation Schemas
# =============================================================================


class GenerateRequest(BaseModel):
    """Request to generate images."""

    plan_id: str
    item_ids: list[str] = Field(default_factory=list)  # Empty = all approved


class GenerationProgress(BaseModel):
    """Progress update during generation."""

    plan_id: str
    item_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int  # 0-100
    message: str | None = None
    output_path: str | None = None


class GenerationResult(BaseModel):
    """Result of a generation."""

    item_id: str
    success: bool
    output_path: str | None = None
    error: str | None = None
    cost_usd: float = 0.0


class GenerateResponse(BaseModel):
    """Response from generation."""

    plan_id: str
    results: list[GenerationResult]
    total_cost: float


# =============================================================================
# WebSocket Messages
# =============================================================================


class WSMessage(BaseModel):
    """WebSocket message wrapper."""

    type: Literal["chat", "plan", "progress", "error", "ping", "pong"]
    data: dict


# Forward reference update
ChatResponse.model_rebuild()
