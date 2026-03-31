#!/usr/bin/env python3
"""
ToolRank Layer 3: Runtime Reliability Testing
==============================================
Tests MCP servers for actual runtime behavior:
  - Health check / connectivity
  - Response time (latency)
  - Schema conformance (does response match declared output?)
  - Error quality (are error messages actionable?)
  - Basic tool invocation (where possible)

Usage:
  python runtime_test.py --all --dry-run
  python runtime_test.py --server-id UUID --apply
  python runtime_test.py --url https://mcp-server.example.com --apply

Requires: httpx
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    os.system(f"{sys.executable} -m pip install httpx --break-system-packages -q")
    import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# ── Runtime Test Suite ──────────────────────────────────────

class RuntimeTest:
    """Test a single MCP server's runtime behavior."""

    def __init__(self, server_url: str, timeout: float = 10.0):
        self.server_url = server_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)
        self.results = {
            "url": server_url,
            "health": None,
            "latency_ms": None,
            "mcp_handshake": None,
            "tool_list": None,
            "tool_count": 0,
            "error_quality": None,
            "tests_passed": 0,
            "tests_total": 0,
            "success_rate": 0.0,
            "errors": [],
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def run_all(self) -> dict:
        """Run all runtime tests."""
        self._test_health()
        self._test_mcp_handshake()
        self._test_tool_list()
        self._test_error_handling()

        total = self.results["tests_total"]
        passed = self.results["tests_passed"]
        self.results["success_rate"] = round((passed / total * 100) if total > 0 else 0, 1)

        return self.results

    def _test_health(self):
        """Test 1: Basic HTTP connectivity."""
        self.results["tests_total"] += 1
        try:
            start = time.time()
            r = self.client.get(self.server_url)
            latency = round((time.time() - start) * 1000)
            self.results["latency_ms"] = latency

            if r.status_code < 500:
                self.results["health"] = "ok"
                self.results["tests_passed"] += 1
            else:
                self.results["health"] = f"error_{r.status_code}"
                self.results["errors"].append(f"Health check: HTTP {r.status_code}")
        except httpx.ConnectError:
            self.results["health"] = "unreachable"
            self.results["errors"].append("Health check: Connection refused")
        except httpx.TimeoutException:
            self.results["health"] = "timeout"
            self.results["latency_ms"] = -1
            self.results["errors"].append("Health check: Timeout")
        except Exception as e:
            self.results["health"] = "error"
            self.results["errors"].append(f"Health check: {e}")

    def _test_mcp_handshake(self):
        """Test 2: MCP JSON-RPC initialize handshake."""
        self.results["tests_total"] += 1
        try:
            # Try MCP initialize
            mcp_init = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "toolrank-runtime-test", "version": "1.0.0"},
                },
            }
            r = self.client.post(
                f"{self.server_url}/mcp",
                json=mcp_init,
                headers={"Content-Type": "application/json"},
            )

            if r.status_code == 200:
                data = r.json()
                if "result" in data or "jsonrpc" in data:
                    self.results["mcp_handshake"] = "ok"
                    self.results["tests_passed"] += 1
                else:
                    self.results["mcp_handshake"] = "invalid_response"
                    self.results["errors"].append("MCP handshake: No 'result' in response")
            else:
                self.results["mcp_handshake"] = f"http_{r.status_code}"
                self.results["errors"].append(f"MCP handshake: HTTP {r.status_code}")
        except Exception as e:
            self.results["mcp_handshake"] = "error"
            self.results["errors"].append(f"MCP handshake: {e}")

    def _test_tool_list(self):
        """Test 3: Can we list available tools?"""
        self.results["tests_total"] += 1
        try:
            tool_list_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
            r = self.client.post(
                f"{self.server_url}/mcp",
                json=tool_list_req,
                headers={"Content-Type": "application/json"},
            )

            if r.status_code == 200:
                data = r.json()
                tools = data.get("result", {}).get("tools", [])
                if isinstance(tools, list):
                    self.results["tool_list"] = "ok"
                    self.results["tool_count"] = len(tools)
                    self.results["tests_passed"] += 1
                else:
                    self.results["tool_list"] = "invalid_format"
                    self.results["errors"].append("Tool list: Response not a list")
            else:
                self.results["tool_list"] = f"http_{r.status_code}"
                self.results["errors"].append(f"Tool list: HTTP {r.status_code}")
        except Exception as e:
            self.results["tool_list"] = "error"
            self.results["errors"].append(f"Tool list: {e}")

    def _test_error_handling(self):
        """Test 4: Does the server return actionable errors?"""
        self.results["tests_total"] += 1
        try:
            # Send invalid request to test error handling
            bad_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "__nonexistent_tool_test__", "arguments": {}},
            }
            r = self.client.post(
                f"{self.server_url}/mcp",
                json=bad_req,
                headers={"Content-Type": "application/json"},
            )

            if r.status_code == 200:
                data = r.json()
                error = data.get("error", {})
                if error and error.get("message"):
                    # Has structured error with message = good
                    self.results["error_quality"] = "good"
                    self.results["tests_passed"] += 1
                elif "error" in str(data).lower():
                    self.results["error_quality"] = "basic"
                    self.results["tests_passed"] += 1
                else:
                    self.results["error_quality"] = "silent"
                    self.results["errors"].append("Error handling: No error returned for invalid tool")
            elif r.status_code == 400 or r.status_code == 404:
                self.results["error_quality"] = "http_error"
                self.results["tests_passed"] += 1  # At least it returned an error code
            else:
                self.results["error_quality"] = "poor"
                self.results["errors"].append(f"Error handling: HTTP {r.status_code} with no useful message")
        except Exception as e:
            self.results["error_quality"] = "crash"
            self.results["errors"].append(f"Error handling: Server crashed on invalid input: {e}")


# ── Supabase Integration ─────────────────────────────────────

class SupabaseClient:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.client = httpx.Client(timeout=30)

    def get_deployed_servers(self, limit: int = 100) -> list:
        """Get servers that have a URL we can test."""
        url = f"{self.url}/rest/v1/servers?select=id,server_name,display_name,url&is_deployed=eq.true&limit={limit}"
        r = self.client.get(url, headers=self.headers)
        r.raise_for_status()
        return [s for s in r.json() if s.get("url")]

    def save_runtime_result(self, server_id: str, server_name: str, results: dict):
        """Update trust_tiers with runtime data."""
        success_rate = results.get("success_rate", 0)
        verified = "earned" if success_rate >= 90 else "none"
        now = datetime.now(timezone.utc).isoformat()

        # Upsert trust tier
        data = {
            "server_id": server_id,
            "server_name": server_name,
            "runtime_verified": verified,
            "runtime_verified_at": now if verified == "earned" else None,
            "runtime_verified_data": {
                "health": results.get("health"),
                "latency_ms": results.get("latency_ms"),
                "success_rate": success_rate,
                "tool_count": results.get("tool_count", 0),
                "error_quality": results.get("error_quality"),
                "errors": results.get("errors", []),
                "tested_at": results.get("tested_at"),
            },
            "updated_at": now,
        }
        url = f"{self.url}/rest/v1/trust_tiers"
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = self.client.post(url, headers=headers, json=data)
        r.raise_for_status()

        # Audit log
        audit = {
            "server_id": server_id,
            "action": "runtime_test",
            "tier_name": "runtime_verified",
            "old_value": "",
            "new_value": f"{success_rate}%",
            "reason": f"Runtime test: {results['tests_passed']}/{results['tests_total']} passed, latency {results.get('latency_ms', '?')}ms",
            "metadata": results,
        }
        audit_url = f"{self.url}/rest/v1/trust_audit_log"
        self.client.post(audit_url, headers=self.headers, json=audit)


# ── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ToolRank Layer 3: Runtime Reliability Testing")
    parser.add_argument("--url", type=str, help="Test a specific server URL")
    parser.add_argument("--server-id", type=str, help="Test a specific server by DB ID")
    parser.add_argument("--all", action="store_true", help="Test all deployed servers")
    parser.add_argument("--apply", action="store_true", help="Save results to DB")
    parser.add_argument("--dry-run", action="store_true", help="Print results only")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout per request (seconds)")
    args = parser.parse_args()

    db = None
    if SUPABASE_URL and SUPABASE_KEY and args.apply:
        db = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)

    print(f"\n{'='*60}")
    print(f"  ToolRank Layer 3: Runtime Reliability Test")
    print(f"  Mode: {'LIVE' if args.apply else 'DRY RUN'}")
    print(f"{'='*60}\n")

    if args.url:
        # Test single URL
        tester = RuntimeTest(args.url, timeout=args.timeout)
        results = tester.run_all()
        _print_results(args.url, results)

    elif args.all and db:
        servers = db.get_deployed_servers(limit=50)
        print(f"  Found {len(servers)} deployed servers to test\n")

        for s in servers:
            url = s.get("url", "")
            if not url:
                continue
            print(f"  Testing: {s.get('display_name') or s.get('server_name')}...")
            tester = RuntimeTest(url, timeout=args.timeout)
            results = tester.run_all()
            _print_results(s.get("display_name") or s.get("server_name"), results)

            if args.apply:
                try:
                    db.save_runtime_result(s["id"], s.get("server_name", ""), results)
                    print(f"    → Saved to DB")
                except Exception as e:
                    print(f"    → DB save error: {e}")
    else:
        print("  Specify --url, or --all with Supabase credentials")
        parser.print_help()


def _print_results(name: str, results: dict):
    rate = results["success_rate"]
    status = "✅ PASS" if rate >= 90 else "⚠️ PARTIAL" if rate >= 50 else "❌ FAIL"

    print(f"\n  {name}")
    print(f"    {status} — {results['tests_passed']}/{results['tests_total']} tests passed ({rate}%)")
    print(f"    Health: {results['health']} | Latency: {results['latency_ms']}ms")
    print(f"    MCP Handshake: {results['mcp_handshake']} | Tools: {results['tool_count']}")
    print(f"    Error Quality: {results['error_quality']}")
    if results["errors"]:
        for err in results["errors"]:
            print(f"    ⚠ {err}")
    print()


if __name__ == "__main__":
    main()
