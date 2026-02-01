"""
Simple test to verify Docker containers are working.

Tests basic connectivity and endpoints without needing AI APIs.
"""

import sys

import httpx


def test_backend():
    """Test backend is responding."""
    print("Testing Backend...")

    try:
        # Health check
        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        print(f"   [OK] Health: {data['status']}")
        print(f"   [OK] Version: {data['version']}")

        # Root endpoint
        response = httpx.get("http://localhost:8000/", timeout=5.0)
        assert response.status_code == 200
        print("   [OK] Root endpoint OK")

        # API docs
        response = httpx.get("http://localhost:8000/docs", timeout=5.0)
        assert response.status_code == 200
        print("   [OK] API docs available at http://localhost:8000/docs")

        # Brands endpoint
        response = httpx.get("http://localhost:8000/api/v1/brands", timeout=5.0)
        assert response.status_code == 200
        brands = response.json()
        print(f"   [OK] Brands endpoint: {brands['total']} brands loaded")

        return True

    except Exception as e:
        print(f"   [FAIL] Backend test failed: {e}")
        return False


def test_frontend():
    """Test frontend is responding. Tries 3001 first (Docker), then 3000."""
    print("\nTesting Frontend...")
    for port in (3001, 3000):
        try:
            response = httpx.get(f"http://localhost:{port}", timeout=10.0)
            if response.status_code == 200:
                print(f"   [OK] Frontend responding on port {port}")
                print(f"   [INFO] Open http://localhost:{port} in your browser")
                return True
        except Exception:
            continue
    print("   [FAIL] Frontend not responding on 3000 or 3001")
    return False


def main():
    """Run all tests."""
    print("Testing CM-Agents Docker Setup\n")
    print("=" * 60)

    backend_ok = test_backend()
    frontend_ok = test_frontend()

    print("\n" + "=" * 60)

    if backend_ok and frontend_ok:
        print("[PASS] ALL TESTS PASSED!")
        print("\nNext steps:")
        print("   1. Open http://localhost:3001 (or :3000) in your browser")
        print("   2. Open http://localhost:8000/docs for API documentation")
        print("   3. Backend logs: docker compose logs backend")
        print("   4. Frontend logs: docker compose logs frontend")
        print("   5. Stop containers: docker compose down")
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED")
        print("\nTroubleshooting:")
        print("   - Check containers: docker compose ps")
        print("   - View logs: docker compose logs")
        print("   - Restart: docker compose restart")
        return 1


if __name__ == "__main__":
    sys.exit(main())
