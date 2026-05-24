#!/usr/bin/env python3
"""
Test suite intensivo para agentes AI, MCP y flujos.
Usa el endpoint / del core service para probar el flujo completo.
"""

import httpx

CORE_URL = "http://localhost:8080"

results = {"passed": [], "failed": []}


def test_health():
    """Test health endpoint"""
    print("\n--- Testing Health Endpoint ---")
    
    try:
        resp = httpx.get(f"{CORE_URL}/health", timeout=10)
        data = resp.json()
        
        checks = ["redis", "db_hotel", "db_payments", "ollama", "system_payment"]
        for check in checks:
            if data.get(check) == "ok":
                results["passed"].append(f"health.{check}")
                print(f"✓ PASS: health.{check}")
            else:
                results["failed"].append((f"health.{check}", data.get(check, "error")))
                print(f"✗ FAIL: health.{check} - {data.get(check)}")
    except Exception as e:
        print(f"✗ FAIL: health endpoint - {e}")


def test_llm_basic():
    """Test LLM basic interaction"""
    print("\n--- Testing LLM Basic Interaction ---")
    
    test_cases = [
        {"message": "Hola", "name": "TestUser"},
        {"message": "Info del hotel", "name": "TestUser"},
    ]
    
    for tc in test_cases:
        try:
            resp = httpx.post(f"{CORE_URL}/", json=tc, timeout=30)
            data = resp.json()
            if "reply" in data and data["reply"]:
                results["passed"].append(f"llm.basic '{tc['message'][:15]}'")
                print(f"✓ PASS: llm.basic '{tc['message'][:15]}'")
            else:
                results["failed"].append((f"llm.basic", "No reply"))
                print(f"✗ FAIL: llm.basic - No reply")
        except Exception as e:
            results["failed"].append(("llm.basic", str(e)))
            print(f"✗ FAIL: llm.basic - {e}")


def test_admin_check():
    """Test admin check endpoint"""
    print("\n--- Testing Admin Check ---")
    
    try:
        r1 = httpx.post(f"{CORE_URL}/admin/check", json={"phone": "51977972106"}, timeout=10)
        data = r1.json()
        if data.get("is_admin"):
            results["passed"].append("admin.check_authorized")
            print("✓ PASS: admin.check_authorized")
        else:
            results["failed"].append(("admin.check", "Should be admin"))
            print("✗ FAIL: admin.check - should be admin")
        
        r2 = httpx.post(f"{CORE_URL}/admin/check", json={"phone": "51999999999"}, timeout=10)
        data = r2.json()
        if not data.get("is_admin"):
            results["passed"].append("admin.check_non_authorized")
            print("✓ PASS: admin.check_non_authorized")
    except Exception as e:
        results["failed"].append(("admin.check", str(e)))
        print(f"✗ FAIL: admin.check - {e}")


def test_mcp_tools():
    """Test MCP tools through LLM"""
    print("\n--- Testing MCP Tools ---")
    
    queries = [
        ("ver todas las habitaciones", "Ver habitaciones"),
        ("ver todos los clientes", "Ver clientes"),
    ]
    
    for q, label in queries:
        try:
            resp = httpx.post(f"{CORE_URL}/admin/llm", json={"message": q, "name": "Admin"}, timeout=30)
            data = resp.json()
            if "reply" in data:
                results["passed"].append(f"mcp.{label}")
                print(f"✓ PASS: mcp.{label}")
            else:
                results["failed"].append(("mcp", "No reply"))
                print(f"✗ FAIL: mcp.{label} - No reply")
        except Exception as e:
            results["failed"].append(("mcp", str(e)))
            print(f"✗ FAIL: mcp.{label} - {e}")


def main():
    print("="*60)
    print("TEST SUITE INTENSIVO - AGENTES AI")
    print("="*60)
    
    test_health()
    test_llm_basic()
    test_admin_check()
    test_mcp_tools()
    
    total = len(results["passed"]) + len(results["failed"])
    print("\n" + "="*60)
    print(f"RESULTADOS: {len(results['passed'])}/{total} pruebas pasadas")
    print("="*60)
    
    return 0 if len(results["failed"]) == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())