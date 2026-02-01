"""Campaign management routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..schemas import CampaignListResponse, CampaignSummary

router = APIRouter()


def get_brands_dir() -> Path:
    """Get brands directory path."""
    return Path(settings.BRANDS_DIR)


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_all_campaigns():
    """List campaigns across all brands."""
    brands_dir = get_brands_dir()

    if not brands_dir.exists():
        return CampaignListResponse(campaigns=[], total=0)

    campaigns = []
    for brand_path in brands_dir.iterdir():
        if not brand_path.is_dir():
            continue

        campaigns_dir = brand_path / "campaigns"
        if not campaigns_dir.exists():
            continue

        for campaign_path in campaigns_dir.iterdir():
            if not campaign_path.is_dir():
                continue

            try:
                from ...models.campaign import Campaign

                campaign = Campaign.load(campaign_path)
                completed, total = campaign.get_progress()

                campaigns.append(
                    CampaignSummary(
                        name=campaign.name,
                        slug=campaign_path.name,
                        brand=brand_path.name,
                        start_date=campaign.dates.start,
                        end_date=campaign.dates.end,
                        is_active=campaign.is_active(),
                        progress=(completed, total),
                    )
                )
            except Exception:
                continue

    return CampaignListResponse(campaigns=campaigns, total=len(campaigns))


@router.get("/brands/{brand_slug}/campaigns", response_model=CampaignListResponse)
async def list_brand_campaigns(brand_slug: str):
    """List campaigns for a specific brand."""
    brand_path = get_brands_dir() / brand_slug

    if not brand_path.exists():
        raise HTTPException(status_code=404, detail=f"Brand '{brand_slug}' not found")

    campaigns_dir = brand_path / "campaigns"
    if not campaigns_dir.exists():
        return CampaignListResponse(campaigns=[], total=0)

    campaigns = []
    for campaign_path in campaigns_dir.iterdir():
        if not campaign_path.is_dir():
            continue

        try:
            from ...models.campaign import Campaign

            campaign = Campaign.load(campaign_path)
            completed, total = campaign.get_progress()

            campaigns.append(
                CampaignSummary(
                    name=campaign.name,
                    slug=campaign_path.name,
                    brand=brand_slug,
                    start_date=campaign.dates.start,
                    end_date=campaign.dates.end,
                    is_active=campaign.is_active(),
                    progress=(completed, total),
                )
            )
        except Exception:
            continue

    return CampaignListResponse(campaigns=campaigns, total=len(campaigns))


@router.get("/brands/{brand_slug}/campaigns/{campaign_slug}")
async def get_campaign(brand_slug: str, campaign_slug: str):
    """Get full campaign details."""
    campaign_path = get_brands_dir() / brand_slug / "campaigns" / campaign_slug

    if not campaign_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Campaign '{campaign_slug}' not found in brand '{brand_slug}'",
        )

    try:
        from ...models.campaign import Campaign

        campaign = Campaign.load(campaign_path)
        completed, total = campaign.get_progress()

        # Get outputs
        outputs_dir = campaign_path / "outputs"
        outputs = []
        if outputs_dir.exists():
            outputs = [
                f.name for f in outputs_dir.iterdir() if f.suffix in (".png", ".jpg", ".webp")
            ]

        return {
            "slug": campaign_slug,
            "brand": brand_slug,
            "name": campaign.name,
            "description": campaign.description,
            "dates": campaign.dates.model_dump(),
            "theme": campaign.theme.model_dump(),
            "products": campaign.products,
            "content_plan": [item.model_dump() for item in campaign.content_plan],
            "hashtags_extra": campaign.hashtags_extra,
            "is_active": campaign.is_active(),
            "progress": {"completed": completed, "total": total},
            "outputs": outputs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
