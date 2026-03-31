"""
ToolRank SDK — Trust-aware tool selection for AI agent frameworks.

Integrates with LangChain, CrewAI, and any Python agent framework.
Provides trust-filtered tool selection based on ToolRank verification data.

Install:
    pip install toolrank

Usage:
    from toolrank import ToolRank

    tr = ToolRank()
    trusted = tr.get_trusted_tools(min_trust=2)
    status = tr.get_trust_status("server-uuid")
    score = tr.score_tool({"name": "my_tool", "description": "..."})
    rewrite = tr.rewrite_tool({"name": "my_tool", "description": "..."})

LangChain integration:
    from toolrank.langchain import ToolRankToolSelector
    selector = ToolRankToolSelector(min_trust=2)
    filtered_tools = selector.filter(tools)

CrewAI integration:
    from toolrank.crewai import trust_filter
    @trust_filter(min_trust=1)
    def get_tools(): ...
"""

__version__ = "0.1.0"

try:
    import httpx
    _CLIENT_CLASS = httpx.Client
except ImportError:
    import urllib.request
    import json as _json
    _CLIENT_CLASS = None


class ToolRank:
    """ToolRank API client for trust-aware tool selection."""

    BASE_URL = "https://mcp.toolrank.dev"

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.api_key = api_key
        self._client = _CLIENT_CLASS(timeout=30) if _CLIENT_CLASS else None

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url += f"?{qs}"

        if self._client:
            r = self._client.get(url)
            r.raise_for_status()
            return r.json()
        else:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as resp:
                return _json.loads(resp.read())

    def _post(self, path: str, data: dict) -> dict:
        url = f"{self.base_url}{path}"
        if self._client:
            r = self._client.post(url, json=data)
            r.raise_for_status()
            return r.json()
        else:
            body = _json.dumps(data).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                return _json.loads(resp.read())

    # ── Core API ────────────────────────────────────────────

    def get_trust_status(self, server_id: str) -> dict:
        """Get full trust profile for a server.

        Returns:
            dict with trust_level, spec, selection, runtime verification data.

        Example:
            >>> tr = ToolRank()
            >>> status = tr.get_trust_status("625fe862-edc2-4658-b174-8540a6cb3e4f")
            >>> print(status["trust_level"])  # 0, 1, 2, or 3
        """
        return self._get(f"/api/trust-status/{server_id}")

    def get_trusted_tools(self, min_trust: int = 1, limit: int = 50) -> list:
        """Get list of servers meeting minimum trust level.

        Args:
            min_trust: Minimum trust level (0=any, 1=Spec, 2=Selection, 3=Full)
            limit: Max results (default 50)

        Returns:
            List of server dicts with server_id, server_name, trust_level, etc.

        Example:
            >>> trusted = tr.get_trusted_tools(min_trust=2)
            >>> for server in trusted:
            ...     print(f"{server['server_name']}: trust {server['trust_level']}")
        """
        result = self._get("/api/trusted-list", {"min_trust": min_trust, "limit": limit})
        return result.get("servers", [])

    def score_tool(self, tool: dict) -> dict:
        """Score a tool definition.

        Args:
            tool: MCP tool definition with name, description, inputSchema.

        Returns:
            dict with score, level, percentile, dimensions, issues.

        Example:
            >>> result = tr.score_tool({
            ...     "name": "search_repos",
            ...     "description": "Search GitHub repositories by keyword.",
            ...     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}
            ... })
            >>> print(result["score"])  # 0-100
        """
        return self._post("/api/score", {"tools": [tool] if "name" in tool else tool})

    def rewrite_tool(self, tool: dict) -> dict:
        """Get AI-powered rewrite proposal for a tool definition (Pro).

        Args:
            tool: MCP tool definition to optimize.

        Returns:
            dict with original score, rewritten tool, rewritten score, improvement.

        Example:
            >>> result = tr.rewrite_tool({"name": "get", "description": "gets stuff"})
            >>> print(result["rewritten"])  # Optimized tool definition
            >>> print(result["improvement"])  # Score improvement (e.g., +25)
        """
        return self._post("/api/rewrite", {"tool": tool})

    def is_trusted(self, server_id: str, min_trust: int = 1) -> bool:
        """Check if a server meets minimum trust level.

        Example:
            >>> if tr.is_trusted("server-uuid", min_trust=2):
            ...     print("Safe to use")
        """
        try:
            status = self.get_trust_status(server_id)
            return status.get("trust_level", 0) >= min_trust
        except Exception:
            return False


# ── LangChain Integration ────────────────────────────────

class LangChainToolFilter:
    """Filter LangChain tools by ToolRank trust level.

    Usage:
        from toolrank import ToolRank, LangChainToolFilter
        from langchain.tools import Tool

        tr = ToolRank()
        tf = LangChainToolFilter(tr, min_trust=2)

        # Filter a list of tools
        tools = [Tool(...), Tool(...)]
        trusted_tools = tf.filter(tools, server_ids={"tool_name": "server-uuid"})
    """

    def __init__(self, client: ToolRank = None, min_trust: int = 1):
        self.client = client or ToolRank()
        self.min_trust = min_trust
        self._cache: dict = {}

    def check(self, server_id: str) -> bool:
        """Check if a server is trusted (cached)."""
        if server_id not in self._cache:
            self._cache[server_id] = self.client.is_trusted(server_id, self.min_trust)
        return self._cache[server_id]

    def filter(self, tools: list, server_ids: dict = None) -> list:
        """Filter tools, keeping only those from trusted servers.

        Args:
            tools: List of LangChain Tool objects.
            server_ids: Mapping of tool.name -> ToolRank server_id.

        Returns:
            Filtered list of tools that meet trust threshold.
        """
        if not server_ids:
            return tools  # No mapping, return all
        return [t for t in tools if self.check(server_ids.get(t.name, ""))]


# ── CrewAI Integration ───────────────────────────────────

def trust_filter(min_trust: int = 1, client: ToolRank = None):
    """Decorator to filter CrewAI tool results by trust level.

    Usage:
        from toolrank import trust_filter

        @trust_filter(min_trust=2)
        def get_agent_tools():
            return [tool1, tool2, tool3]
    """
    _client = client or ToolRank()

    def decorator(func):
        def wrapper(*args, **kwargs):
            tools = func(*args, **kwargs)
            trusted = _client.get_trusted_tools(min_trust=min_trust, limit=100)
            trusted_names = {s["server_name"] for s in trusted}
            return [t for t in tools if getattr(t, "name", "") in trusted_names]
        return wrapper
    return decorator
