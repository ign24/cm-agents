"""Brand management routes."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..schemas import BrandListResponse, BrandSummary
from ..security import RateLimitDep, safe_slug, validate_file_extension

router = APIRouter()


def get_brands_dir() -> Path:
    """Get brands directory path."""
    return Path(settings.BRANDS_DIR)


@router.get("/brands", response_model=BrandListResponse)
async def list_brands(_: RateLimitDep):
    """List all available brands."""
    brands_dir = get_brands_dir()

    if not brands_dir.exists():
        return BrandListResponse(brands=[], total=0)

    brands = []
    for brand_path in brands_dir.iterdir():
        if not brand_path.is_dir():
            continue

        brand_json = brand_path / "brand.json"
        if not brand_json.exists():
            continue

        try:
            from ...models.brand import Brand

            brand = Brand.load(brand_path)

            # Count campaigns
            campaigns_dir = brand_path / "campaigns"
            campaigns_count = 0
            if campaigns_dir.exists():
                campaigns_count = len([d for d in campaigns_dir.iterdir() if d.is_dir()])

            # Get logo URL
            logo_path = brand.get_logo_path(brand_path)
            logo_url = f"/api/v1/brands/{brand_path.name}/logo" if logo_path else None

            brands.append(
                BrandSummary(
                    name=brand.name,
                    slug=brand_path.name,
                    industry=brand.industry,
                    logo_url=logo_url,
                    campaigns_count=campaigns_count,
                )
            )
        except Exception:
            # Skip invalid brands
            continue

    return BrandListResponse(brands=brands, total=len(brands))


@router.get("/brands/{slug}")
async def get_brand(slug: str, _: RateLimitDep):
    """Get full brand details."""
    # Validate slug to prevent path traversal
    slug = safe_slug(slug)
    brand_path = get_brands_dir() / slug

    if not brand_path.exists():
        raise HTTPException(status_code=404, detail=f"Brand '{slug}' not found")

    brand_json = brand_path / "brand.json"
    if not brand_json.exists():
        raise HTTPException(status_code=404, detail="Brand config not found")

    try:
        from ...models.brand import Brand

        brand = Brand.load(brand_path)

        # Get campaigns
        campaigns_dir = brand_path / "campaigns"
        campaigns = []
        if campaigns_dir.exists():
            campaigns = [d.name for d in campaigns_dir.iterdir() if d.is_dir()]

        # Get logo path
        logo_path = brand.get_logo_path(brand_path)

        return {
            "slug": slug,
            "name": brand.name,
            "handle": brand.handle,
            "industry": brand.industry,
            "identity": brand.identity.model_dump() if brand.identity else None,
            "palette": brand.palette.model_dump(),
            "style": brand.style.model_dump(),
            "typography": brand.typography.model_dump() if brand.typography else None,
            "assets": {
                "logo": f"/api/v1/brands/{slug}/logo" if logo_path else None,
            },
            "campaigns": campaigns,
            "preferred_styles": brand.get_preferred_styles(),
            "avoid_styles": brand.get_avoid_styles(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brands/{slug}/logo")
async def get_brand_logo(slug: str, _: RateLimitDep):
    """Get brand logo image."""
    # Validate slug to prevent path traversal
    slug = safe_slug(slug)
    brand_path = get_brands_dir() / slug

    if not brand_path.exists():
        raise HTTPException(status_code=404, detail=f"Brand '{slug}' not found")

    try:
        from ...models.brand import Brand

        brand = Brand.load(brand_path)
        logo_path = brand.get_logo_path(brand_path)

        if not logo_path:
            raise HTTPException(status_code=404, detail="Logo not found")

        # Validate file extension
        if not validate_file_extension(logo_path.name):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Ensure logo is within brand directory (prevent traversal)
        try:
            logo_path.resolve().relative_to(brand_path.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid logo path")

        # Get MIME type
        mime_type, _ = mimetypes.guess_type(str(logo_path))

        return FileResponse(
            logo_path,
            media_type=mime_type or "application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
