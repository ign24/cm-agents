"""Demo generator for testing without using real AI APIs."""

import asyncio
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class DemoImageGenerator:
    """
    Generates demo images for testing without calling AI APIs.

    Creates simple placeholder images with text overlay.
    """

    def __init__(self):
        self.cost_per_image = 0.0  # Demo mode is free

    async def generate_demo_image(
        self,
        product_name: str,
        brand_name: str,
        size: str,
        style: str,
        output_dir: Path,
        index: int = 1,
    ) -> tuple[Path, float]:
        """
        Generate a demo image.

        Args:
            product_name: Name of the product
            brand_name: Name of the brand
            size: 'feed' or 'story'
            style: Design style
            output_dir: Where to save the image
            index: Variant number

        Returns:
            Tuple of (image_path, cost)
        """
        # Simulate processing time
        await asyncio.sleep(0.5)

        # Determine image dimensions
        if size == "feed":
            width, height = 1080, 1350
        else:  # story
            width, height = 1080, 1920

        # Create image
        img = Image.new("RGB", (width, height), color=(245, 245, 245))
        draw = ImageDraw.Draw(img)

        # Try to load a font, fallback to default
        try:
            font_large = ImageFont.truetype("arial.ttf", 80)
            font_medium = ImageFont.truetype("arial.ttf", 50)
            font_small = ImageFont.truetype("arial.ttf", 30)
        except Exception:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw centered text
        text_lines = [
            ("[DEMO]", font_small, (150, 150, 150)),
            (product_name, font_large, (50, 50, 50)),
            (brand_name, font_medium, (100, 100, 100)),
            (f"Style: {style}", font_small, (150, 150, 150)),
            (f"Size: {size.upper()}", font_small, (150, 150, 150)),
        ]

        y_offset = height // 3
        for text, font, color in text_lines:
            # Get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Center horizontally
            x = (width - text_width) // 2

            # Draw text
            draw.text((x, y_offset), text, fill=color, font=font)
            y_offset += text_height + 30

        # Add border
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(200, 200, 200), width=5)

        # Save image
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{product_name}_{size}_{index:02d}_demo.png"
        output_path = output_dir / filename

        img.save(output_path, "PNG")
        logger.info(f"Generated demo image: {output_path}")

        return output_path, self.cost_per_image


# Global instance
demo_generator = DemoImageGenerator()
