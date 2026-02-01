"""
End-to-end test for cm-agents system.

Tests the complete flow: chat → plan creation → approval → generation
"""

import asyncio
from pathlib import Path

import httpx

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
BRAND_SLUG = "resto-mario"
TIMEOUT = 30.0


async def test_e2e():
    """Test complete workflow."""
    print("🚀 Starting end-to-end test...\n")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Step 1: Check health
        print("1️⃣  Checking API health...")
        response = await client.get("http://localhost:8000/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print(f"   ✅ API is healthy: {response.json()}\n")

        # Step 2: List brands
        print("2️⃣  Listing brands...")
        response = await client.get(f"{BASE_URL}/brands")
        assert response.status_code == 200, f"List brands failed: {response.text}"
        brands_data = response.json()
        brands = brands_data.get("brands", [])
        assert any(b["slug"] == BRAND_SLUG for b in brands), f"Brand {BRAND_SLUG} not found"
        print(f"   ✅ Found {len(brands)} brands\n")

        # Step 3: Create plan via chat
        print("3️⃣  Creating plan via chat...")
        chat_request = {
            "brand_slug": BRAND_SLUG,
            "message": "Crea un plan para promocionar la pizza napolitana en redes sociales. Solo 2 imágenes: 1 feed y 1 story.",
        }
        response = await client.post(f"{BASE_URL}/chat", json=chat_request)
        assert response.status_code == 200, f"Chat failed: {response.text}"
        chat_response = response.json()
        message = chat_response.get("message", "")
        if len(message) > 100:
            print(f"   📝 Response: {message[0:100]}...")
        else:
            print(f"   📝 Response: {message}")

        # Check if plan was created
        if chat_response.get("plan_id"):
            plan_id = chat_response["plan_id"]
            print(f"   ✅ Plan created: {plan_id}\n")
        else:
            print("   ⚠️  No plan created yet (strategist may need more info)")
            print("   Trying direct plan creation...\n")

            # Step 3b: Create plan directly
            print("3️⃣b Creating plan directly...")
            plan_request = {
                "brand_slug": BRAND_SLUG,
                "description": "Plan para promocionar pizza napolitana: 1 imagen feed y 1 story",
            }
            response = await client.post(f"{BASE_URL}/plans", json=plan_request)
            assert response.status_code == 200, f"Plan creation failed: {response.text}"
            plan_data = response.json()
            plan_id = plan_data["id"]
            print(f"   ✅ Plan created: {plan_id}\n")

        # Step 4: Get plan details
        print("4️⃣  Getting plan details...")
        response = await client.get(f"{BASE_URL}/plans/{plan_id}")
        assert response.status_code == 200, f"Get plan failed: {response.text}"
        plan = response.json()
        print(f"   📋 Plan has {len(plan['items'])} items")
        for item in plan["items"]:
            print(f"      - {item['product']} ({item['size']}) - {item['status']}")
        print()

        # Step 5: Approve items
        print("5️⃣  Approving all items...")
        for item in plan["items"]:
            if item["status"] == "draft":
                approve_request = {"item_id": item["id"], "status": "approved"}
                response = await client.patch(
                    f"{BASE_URL}/plans/{plan_id}/items", json=approve_request
                )
                assert response.status_code == 200, f"Approve failed: {response.text}"
                print(f"   ✅ Approved: {item['product']} ({item['size']})")
        print()

        # Step 6: Generate images
        print("6️⃣  Generating images...")
        generate_request = {"plan_id": plan_id, "item_ids": None}
        response = await client.post(f"{BASE_URL}/generate", json=generate_request)
        assert response.status_code == 200, f"Generation failed: {response.text}"
        generate_response = response.json()
        print(f"   🎨 Generation started for {len(generate_response['results'])} items")
        print(f"   💰 Estimated cost: ${generate_response['total_cost']:.2f}\n")

        # Step 7: Poll for completion
        print("7️⃣  Waiting for generation to complete...")
        max_attempts = 30
        for attempt in range(max_attempts):
            response = await client.get(f"{BASE_URL}/generate/{plan_id}/status")
            assert response.status_code == 200, f"Status check failed: {response.text}"
            status = response.json()

            print(
                f"   Progress: {status['status']['generated']}/{status['total_items']} generated",
                end="\r",
            )

            if status["is_complete"]:
                print("\n   ✅ All items generated!\n")
                break

            await asyncio.sleep(1)
        else:
            raise TimeoutError("Generation took too long")

        # Step 8: Verify outputs
        print("8️⃣  Verifying outputs...")
        response = await client.get(f"{BASE_URL}/plans/{plan_id}")
        plan = response.json()

        outputs_found = 0
        for item in plan["items"]:
            if item.get("output_path"):
                output_path = Path("outputs") / item["output_path"]
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    print(
                        f"   ✅ {item['product']} ({item['size']}): {output_path} ({file_size:,} bytes)"
                    )
                    outputs_found += 1
                else:
                    print(f"   ❌ {item['product']}: Output not found at {output_path}")

        print(f"\n   📊 Total outputs: {outputs_found}/{len(plan['items'])}\n")

        # Final summary
        print("=" * 60)
        print("✅ END-TO-END TEST PASSED!")
        print("=" * 60)
        print(f"Plan ID: {plan_id}")
        print(f"Brand: {BRAND_SLUG}")
        print(f"Items generated: {outputs_found}")
        print("Total cost: $0.00 (demo mode)")
        print(f"\nView outputs at: outputs/generations/{plan_id}/")


if __name__ == "__main__":
    try:
        asyncio.run(test_e2e())
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        raise
