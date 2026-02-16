#!/usr/bin/env python
"""Test script para debuggear campaign detection."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cm_agents.agents.strategist import StrategistAgent
from cm_agents.models.brand import Brand

# Setup
    brand_dir = Path("brands/mi-marca")
brand = Brand.load(brand_dir)

# Create strategist
strategist = StrategistAgent()

# Test prompt
prompt = (
    "campaña black friday para sprite y coca-cola. Los precios son sprite $1.99 y coca-cola $2.50"
)

print(f"\n{'=' * 80}")
print("TESTING CAMPAIGN DETECTION")
print(f"{'=' * 80}")
print(f"Prompt: {prompt}")
print(f"Brand: {brand.name} ({brand_dir.name})")
print(f"{'=' * 80}\n")

# Create plan
try:
    plan = strategist.create_plan(
        prompt=prompt,
        brand=brand,
        brand_dir=brand_dir,
    )

    print(f"\n{'=' * 80}")
    print("PLAN CREATED")
    print(f"{'=' * 80}")
    print(f"Plan ID: {plan.id}")
    print(f"Items: {len(plan.items)}")

    for i, item in enumerate(plan.items, 1):
        print(f"\nItem {i}:")
        print(f"  Product: {item.product}")
        print(f"  Size: {item.size}")
        print(f"  Style: {item.style}")
        print(f"  Price Override: {item.price_override}")
        print(f"  Reference Query: {item.reference_query}")

    print(f"\n{'=' * 80}\n")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback

    traceback.print_exc()
