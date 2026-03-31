# ToolRank Distribution Integration API

## Overview

ToolRank isn't just a scoring site — it's **trust infrastructure** for the MCP ecosystem.

Registries, marketplaces, and agent frameworks can integrate ToolRank trust signals to:
- Surface verified servers above unverified ones
- Show trust badges in search results
- Gate installations behind trust thresholds
- Power "trusted by default" recommendations

## Endpoints

### 1. Trust Status (Single Server)

```
GET https://toolrank.dev/api/trust-status/{server_id}.json
```

**Response:**
```json
{
  "server_id": "mcp-filesystem",
  "server_name": "Filesystem MCP Server",
  "trust_level": 2,
  "trust_label": "Selection Verified",
  "spec": {
    "verified": true,
    "score": 92,
    "verified_at": "2026-03-15T10:00:00Z",
    "expires_at": null
  },
  "selection": {
    "verified": true,
    "win_rate": 78.5,
    "total_rounds": 100,
    "verified_at": "2026-03-20T14:30:00Z",
    "expires_at": "2026-04-20T14:30:00Z"
  },
  "runtime": {
    "verified": false,
    "data": {},
    "verified_at": null,
    "expires_at": null
  },
  "recommended": true,
  "deployment_safe": true,
  "audit_url": "https://toolrank.dev/trust/mcp-filesystem/audit",
  "details_url": "https://toolrank.dev/servers/mcp-filesystem",
  "badge_url": "https://toolrank.dev/api/trust-badge/mcp-filesystem.svg"
}
```

### 2. Trusted List (Category)

```
GET https://toolrank.dev/api/trusted-list.json?category=filesystem&min_trust=1&limit=20
```

**Response:**
```json
{
  "category": "filesystem",
  "min_trust_level": 1,
  "count": 12,
  "servers": [
    {
      "server_id": "mcp-filesystem",
      "server_name": "Filesystem MCP Server",
      "trust_level": 2,
      "spec_score": 92,
      "selection_rate": 78.5,
      "rank": 1,
      "details_url": "https://toolrank.dev/servers/mcp-filesystem"
    }
  ],
  "_meta": {
    "provider": "ToolRank",
    "api_version": "v1",
    "docs": "https://toolrank.dev/docs/api"
  }
}
```

### 3. Trust Badge (SVG)

```
GET https://toolrank.dev/api/trust-badge/{server_id}.svg
```

Returns an SVG badge showing trust tier. Embed in:

**README:**
```markdown
[![ToolRank Trust](https://toolrank.dev/api/trust-badge/YOUR_ID.svg)](https://toolrank.dev/servers/YOUR_ID)
```

**HTML:**
```html
<img src="https://toolrank.dev/api/trust-badge/YOUR_ID.svg" alt="ToolRank Trust" />
```

## Integration Patterns

### For Registries (MCP.so, Official Registry, Smithery)

```javascript
// Fetch trust status before displaying a server
const trust = await fetch(`https://toolrank.dev/api/trust-status/${serverId}.json`);
const data = await trust.json();

// Use in UI
if (data.recommended) {
  showBadge("ToolRank Verified", data.trust_label);
}

// Sort by trust level
servers.sort((a, b) => b.trust_level - a.trust_level);
```

### For Agent Frameworks (LangChain, CrewAI)

```python
import httpx

def get_trusted_tools(category: str, min_trust: int = 1):
    """Get ToolRank-verified tools for agent selection."""
    r = httpx.get(
        "https://toolrank.dev/api/trusted-list.json",
        params={"category": category, "min_trust": min_trust}
    )
    return r.json()["servers"]

# Use in tool selection
trusted = get_trusted_tools("filesystem", min_trust=2)
# → Only use Selection Verified or higher tools
```

### For CI/CD (GitHub Actions)

```yaml
- uses: imhiroki/toolrank-action@v2
  with:
    mode: pre-release
    min-score: 80
    min-selection-rate: 60
```

## Rate Limits

| Tier | Rate | Cache |
|------|------|-------|
| Free | 100 req/hour | 5 min |
| Pro  | 1000 req/hour | 1 min |
| Enterprise | Unlimited | Real-time |

## Versioning

Current API version: `v1`

All endpoints include `_meta.api_version` in responses. Breaking changes will increment the version with 90-day deprecation notice.
