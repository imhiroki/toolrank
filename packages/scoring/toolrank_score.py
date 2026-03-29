"""
ToolRank Scoring Engine v1.0.0
Level A: Rule-based scoring (zero API cost)

Scores MCP tool definitions across 4 dimensions:
- Findability (25%)
- Clarity (35%)  
- Precision (25%)
- Efficiency (15%)

Based on:
- arXiv 2602.14878: 6 components of tool descriptions
- arXiv 2602.18914: 4-dimensional quality standard (18 smell categories)
- Anthropic Tool Search accuracy data

Version history: see CHANGELOG.md
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

# Scoring version — increment on any scoring logic change
SCORE_VERSION = "1.0.0"
SCORE_VERSION_DATE = "2026-03-29"
from pathlib import Path


def _load_weights() -> dict:
    """Load weights from weights.json if available, else use defaults."""
    weights_file = Path(__file__).parent / "weights.json"
    defaults = {"findability": 25, "clarity": 35, "precision": 25, "efficiency": 15}
    if weights_file.exists():
        try:
            with open(weights_file) as f:
                data = json.load(f)
            return {k: data.get(k, defaults[k]) for k in defaults}
        except Exception:
            pass
    return defaults


WEIGHTS = _load_weights()


@dataclass
class Issue:
    dimension: str
    category: str
    severity: str  # "critical", "warning", "info"
    message: str
    tool_name: str
    fix_suggestion: str
    estimated_impact: int  # predicted score improvement if fixed


@dataclass
class DimensionScore:
    score: float  # 0-25
    max_score: float
    issues: list[Issue] = field(default_factory=list)


@dataclass
class ToolScore:
    tool_name: str
    findability: DimensionScore
    clarity: DimensionScore
    precision: DimensionScore
    efficiency: DimensionScore
    total: float  # 0-100
    level: int  # 0-4 maturity level
    level_name: str
    issues: list[Issue] = field(default_factory=list)


@dataclass
class ServerScore:
    server_name: str
    tools: list[ToolScore]
    average_score: float
    total_issues: int
    critical_issues: int
    top_improvements: list[Issue]  # top 3 highest impact fixes


# --- Clarity Checks (35% weight, max 35 points in weighted score) ---

def check_has_description(tool: dict) -> tuple[float, list[Issue]]:
    """Check if tool has a description at all."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "")
    
    if not desc or not desc.strip():
        return 0.0, [Issue(
            dimension="clarity",
            category="missing_description",
            severity="critical",
            message="Tool has no description",
            tool_name=name,
            fix_suggestion="Add a description explaining what this tool does, when to use it, and what it returns",
            estimated_impact=15
        )]
    return 1.0, []


def check_description_length(tool: dict) -> tuple[float, list[Issue]]:
    """Check description length. Too short = unclear, too long = token waste."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "")
    length = len(desc)
    issues = []
    
    if length < 20:
        return 0.2, [Issue(
            dimension="clarity",
            category="too_short_description",
            severity="critical",
            message=f"Description is only {length} chars. Too short for agents to understand purpose",
            tool_name=name,
            fix_suggestion="Expand to at least 50 chars. Include purpose, when to use, and expected output",
            estimated_impact=10
        )]
    elif length < 50:
        return 0.5, [Issue(
            dimension="clarity",
            category="short_description",
            severity="warning",
            message=f"Description is {length} chars. Consider expanding for better agent understanding",
            tool_name=name,
            fix_suggestion="Add usage context and expected behavior. 80-200 chars is optimal",
            estimated_impact=5
        )]
    elif length > 500:
        return 0.7, [Issue(
            dimension="clarity",
            category="verbose_description",
            severity="info",
            message=f"Description is {length} chars. May consume excessive context tokens",
            tool_name=name,
            fix_suggestion="Consider creating a compact variant under 200 chars",
            estimated_impact=2
        )]
    elif 80 <= length <= 250:
        return 1.0, []
    else:
        return 0.8, []


def check_purpose_statement(tool: dict) -> tuple[float, list[Issue]]:
    """Check if description starts with a clear purpose statement."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "").strip().lower()
    
    # Good patterns: starts with verb or "This tool..."
    purpose_patterns = [
        r"^(get|set|create|update|delete|search|find|list|fetch|send|upload|download|check|validate|convert|generate|analyze|calculate|extract|parse|format|merge|split|filter|sort|count|remove|add|modify|configure|connect|disconnect|enable|disable|start|stop|run|execute|process|handle|manage|monitor|track|log|debug|test|verify|authenticate|authorize|encrypt|decrypt|compress|decompress|export|import|sync|backup|restore|deploy|build|install|uninstall|publish|subscribe|notify|alert|schedule|cancel|retry|reset|clear|flush|refresh|reload|migrate|transform|map|reduce|aggregate|group|join|compare|diff|patch|clone|copy|move|rename|archive)",
        r"^(this tool|this function|this method|this endpoint|this action)",
        r"^(retriev|return|provid|allow|enabl|perform|initiat|trigger|invok)",
    ]
    
    for pattern in purpose_patterns:
        if re.match(pattern, desc):
            return 1.0, []
    
    return 0.5, [Issue(
        dimension="clarity",
        category="unclear_purpose",
        severity="warning",
        message="Description doesn't start with a clear action verb or purpose statement",
        tool_name=name,
        fix_suggestion="Start with a verb: 'Creates...', 'Retrieves...', 'Searches for...' or 'This tool...'",
        estimated_impact=5
    )]


def check_usage_context(tool: dict) -> tuple[float, list[Issue]]:
    """Check if description includes usage context (when to use this tool)."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "").lower()
    
    context_indicators = [
        "use this", "when", "useful for", "ideal for", "designed for",
        "helps", "allows", "enables", "for example", "e.g.", "such as",
        "in case", "if you need", "to accomplish", "suitable for"
    ]
    
    if any(indicator in desc for indicator in context_indicators):
        return 1.0, []
    
    return 0.4, [Issue(
        dimension="clarity",
        category="missing_usage_context",
        severity="warning",
        message="Description lacks usage context (when/why to use this tool)",
        tool_name=name,
        fix_suggestion="Add context: 'Use this when...' or 'Ideal for...' to help agents decide when to select this tool",
        estimated_impact=6
    )]


def check_return_description(tool: dict) -> tuple[float, list[Issue]]:
    """Check if description mentions what the tool returns."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "").lower()
    
    return_indicators = [
        "returns", "return", "outputs", "produces", "yields",
        "responds with", "result", "response", "gives back",
        "provides", "generates"
    ]
    
    if any(indicator in desc for indicator in return_indicators):
        return 1.0, []
    
    return 0.5, [Issue(
        dimension="clarity",
        category="missing_return_info",
        severity="info",
        message="Description doesn't mention what the tool returns",
        tool_name=name,
        fix_suggestion="Add what the tool returns: 'Returns a list of...' or 'Outputs...'",
        estimated_impact=3
    )]


def check_name_description_alignment(tool: dict) -> tuple[float, list[Issue]]:
    """Check if tool name semantically aligns with description."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "").lower()
    
    # Extract key words from name (split by _ or camelCase)
    name_parts = re.split(r'[_\-]', name.lower())
    # Also handle camelCase
    name_parts_camel = re.findall(r'[a-z]+', re.sub(r'([A-Z])', r' \1', name).lower())
    all_parts = set(name_parts + name_parts_camel)
    all_parts.discard('')
    
    if not all_parts or not desc:
        return 0.5, []
    
    # Check how many name parts appear in description
    matches = sum(1 for part in all_parts if part in desc and len(part) > 2)
    ratio = matches / len(all_parts) if all_parts else 0
    
    if ratio >= 0.5:
        return 1.0, []
    elif ratio >= 0.25:
        return 0.7, []
    else:
        return 0.3, [Issue(
            dimension="clarity",
            category="name_description_mismatch",
            severity="warning",
            message=f"Tool name '{name}' doesn't align well with description content",
            tool_name=name,
            fix_suggestion="Ensure description mentions the key concepts from the tool name",
            estimated_impact=4
        )]


# --- Precision Checks (25% weight) ---

def check_input_schema_exists(tool: dict) -> tuple[float, list[Issue]]:
    """Check if inputSchema is defined."""
    name = tool.get("name", "unknown")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})
    
    if not schema:
        return 0.0, [Issue(
            dimension="precision",
            category="missing_schema",
            severity="critical",
            message="No input schema defined",
            tool_name=name,
            fix_suggestion="Add an inputSchema with type definitions for all parameters",
            estimated_impact=12
        )]
    return 1.0, []


def check_parameter_types(tool: dict) -> tuple[float, list[Issue]]:
    """Check if all parameters have type definitions."""
    name = tool.get("name", "unknown")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})
    properties = schema.get("properties", {})
    issues = []
    
    if not properties:
        return 0.5, []  # No parameters might be valid
    
    missing_types = []
    for param_name, param_def in properties.items():
        if "type" not in param_def:
            missing_types.append(param_name)
    
    if missing_types:
        score = max(0, 1.0 - (len(missing_types) / len(properties)))
        issues.append(Issue(
            dimension="precision",
            category="missing_parameter_type",
            severity="warning",
            message=f"Parameters without type definition: {', '.join(missing_types)}",
            tool_name=name,
            fix_suggestion="Add 'type' to each parameter (string, number, boolean, array, object)",
            estimated_impact=4
        ))
        return score, issues
    
    return 1.0, []


def check_parameter_descriptions(tool: dict) -> tuple[float, list[Issue]]:
    """Check if parameters have descriptions."""
    name = tool.get("name", "unknown")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})
    properties = schema.get("properties", {})
    issues = []
    
    if not properties:
        return 0.5, []
    
    missing_desc = []
    for param_name, param_def in properties.items():
        if "description" not in param_def:
            missing_desc.append(param_name)
    
    if missing_desc:
        ratio = len(missing_desc) / len(properties)
        score = max(0, 1.0 - ratio)
        issues.append(Issue(
            dimension="precision",
            category="missing_parameter_description",
            severity="warning",
            message=f"Parameters without description: {', '.join(missing_desc)}",
            tool_name=name,
            fix_suggestion="Add 'description' to each parameter explaining its purpose and valid values",
            estimated_impact=5
        ))
        return score, issues
    
    return 1.0, []


def check_required_fields(tool: dict) -> tuple[float, list[Issue]]:
    """Check if required fields are defined."""
    name = tool.get("name", "unknown")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if not properties:
        return 0.5, []
    
    if not required and len(properties) > 0:
        return 0.5, [Issue(
            dimension="precision",
            category="missing_required_fields",
            severity="info",
            message="No required fields specified. Agents may not know which parameters are mandatory",
            tool_name=name,
            fix_suggestion="Add a 'required' array listing mandatory parameters",
            estimated_impact=3
        )]
    
    return 1.0, []


def check_enum_usage(tool: dict) -> tuple[float, list[Issue]]:
    """Check if string parameters with limited values use enum."""
    name = tool.get("name", "unknown")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})
    properties = schema.get("properties", {})
    issues = []
    
    if not properties:
        return 0.5, []
    
    # Heuristic: parameters with names suggesting limited options
    enum_hint_names = ["type", "format", "mode", "status", "action", "method",
                       "direction", "order", "sort", "level", "priority", "role",
                       "category", "kind", "style", "variant", "size", "unit"]
    
    missing_enum = []
    for param_name, param_def in properties.items():
        if (param_def.get("type") == "string" and
            any(hint in param_name.lower() for hint in enum_hint_names) and
            "enum" not in param_def):
            missing_enum.append(param_name)
    
    if missing_enum:
        return 0.7, [Issue(
            dimension="precision",
            category="missing_enum",
            severity="info",
            message=f"Parameters that might benefit from enum: {', '.join(missing_enum)}",
            tool_name=name,
            fix_suggestion="Add 'enum' arrays for parameters with limited valid values",
            estimated_impact=2
        )]
    
    return 1.0, []


def check_default_values(tool: dict) -> tuple[float, list[Issue]]:
    """Check if optional parameters have default values."""
    name = tool.get("name", "unknown")
    schema = tool.get("inputSchema") or tool.get("input_schema", {})
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    
    if not properties:
        return 0.5, []
    
    optional_without_default = []
    for param_name, param_def in properties.items():
        if param_name not in required and "default" not in param_def:
            optional_without_default.append(param_name)
    
    if optional_without_default and len(optional_without_default) > len(properties) * 0.5:
        return 0.7, [Issue(
            dimension="precision",
            category="missing_defaults",
            severity="info",
            message=f"Optional parameters without defaults: {', '.join(optional_without_default[:5])}",
            tool_name=name,
            fix_suggestion="Add 'default' values to optional parameters to reduce agent confusion",
            estimated_impact=2
        )]
    
    return 1.0, []


# --- Efficiency Checks (15% weight) ---

def check_token_cost(tool: dict) -> tuple[float, list[Issue]]:
    """Estimate token cost of tool definition."""
    name = tool.get("name", "unknown")
    json_str = json.dumps(tool, ensure_ascii=False)
    # Rough estimate: 1 token ≈ 4 chars
    estimated_tokens = len(json_str) / 4
    
    if estimated_tokens > 2000:
        return 0.3, [Issue(
            dimension="efficiency",
            category="high_token_cost",
            severity="warning",
            message=f"Tool definition is ~{int(estimated_tokens)} tokens. This consumes significant context",
            tool_name=name,
            fix_suggestion="Consider creating a compact variant. Shorten descriptions, remove redundant info",
            estimated_impact=3
        )]
    elif estimated_tokens > 1000:
        return 0.6, [Issue(
            dimension="efficiency",
            category="moderate_token_cost",
            severity="info",
            message=f"Tool definition is ~{int(estimated_tokens)} tokens",
            tool_name=name,
            fix_suggestion="Consider trimming description or creating a compact variant",
            estimated_impact=1
        )]
    elif estimated_tokens > 500:
        return 0.8, []
    else:
        return 1.0, []


def check_name_format(tool: dict) -> tuple[float, list[Issue]]:
    """Check if tool name follows best practices for agent discovery."""
    name = tool.get("name", "unknown")
    issues = []
    score = 1.0
    
    # Should be snake_case or camelCase, start with verb
    if not re.match(r'^[a-z][a-zA-Z0-9_]*$', name):
        score -= 0.3
        issues.append(Issue(
            dimension="efficiency",
            category="poor_name_format",
            severity="warning",
            message=f"Tool name '{name}' doesn't follow snake_case or camelCase convention",
            tool_name=name,
            fix_suggestion="Use snake_case (e.g., 'search_users') or camelCase (e.g., 'searchUsers')",
            estimated_impact=3
        ))
    
    # Check if name is too generic
    generic_names = {"run", "execute", "do", "action", "tool", "function", "process", "handle"}
    if name.lower() in generic_names:
        score -= 0.3
        issues.append(Issue(
            dimension="efficiency",
            category="generic_name",
            severity="warning",
            message=f"Tool name '{name}' is too generic for agent discovery",
            tool_name=name,
            fix_suggestion="Use a specific, descriptive name like 'search_repositories' or 'create_issue'",
            estimated_impact=5
        ))
    
    return max(0, score), issues


# --- Findability Checks (25% weight) ---
# Note: Full findability checks require registry API access.
# Level A only checks what's available in the tool definition itself.

def check_tool_name_searchability(tool: dict) -> tuple[float, list[Issue]]:
    """Check if tool name is searchable via BM25/regex."""
    name = tool.get("name", "unknown")
    desc = tool.get("description", "")
    
    # Tools with very short names are hard to find
    if len(name) < 4:
        return 0.4, [Issue(
            dimension="findability",
            category="short_name",
            severity="warning",
            message=f"Tool name '{name}' is very short. May be hard to discover via search",
            tool_name=name,
            fix_suggestion="Use a more descriptive name (e.g., 'get' → 'get_user_profile')",
            estimated_impact=4
        )]
    
    # Names with common domain words are more discoverable
    domain_keywords = desc.lower().split()
    name_words = set(re.split(r'[_\-]', name.lower()))
    
    if not any(w in domain_keywords for w in name_words if len(w) > 3):
        return 0.6, [Issue(
            dimension="findability",
            category="low_searchability",
            severity="info",
            message="Tool name keywords don't overlap with description keywords",
            tool_name=name,
            fix_suggestion="Include domain-relevant words in the tool name for better search matching",
            estimated_impact=3
        )]
    
    return 1.0, []


# --- Main Scoring Function ---

CLARITY_CHECKS = [
    (check_has_description, 5.0),
    (check_description_length, 3.0),
    (check_purpose_statement, 4.0),
    (check_usage_context, 4.0),
    (check_return_description, 2.0),
    (check_name_description_alignment, 3.0),
]

PRECISION_CHECKS = [
    (check_input_schema_exists, 6.0),
    (check_parameter_types, 4.0),
    (check_parameter_descriptions, 4.0),
    (check_required_fields, 3.0),
    (check_enum_usage, 2.0),
    (check_default_values, 2.0),
]

EFFICIENCY_CHECKS = [
    (check_token_cost, 4.0),
    (check_name_format, 4.0),
]

FINDABILITY_CHECKS = [
    (check_tool_name_searchability, 6.0),
]


def score_tool(tool: dict) -> ToolScore:
    """Score a single tool definition across all 4 dimensions."""
    
    all_issues = []
    
    # Score each dimension
    def run_checks(checks, max_points):
        total = 0
        total_weight = sum(w for _, w in checks)
        dim_issues = []
        for check_fn, weight in checks:
            ratio, issues = check_fn(tool)
            total += ratio * weight
            dim_issues.extend(issues)
            all_issues.extend(issues)
        # Normalize to max_points
        return DimensionScore(
            score=round((total / total_weight) * max_points, 1) if total_weight > 0 else 0,
            max_score=max_points,
            issues=dim_issues
        )
    
    findability = run_checks(FINDABILITY_CHECKS, WEIGHTS["findability"])
    clarity = run_checks(CLARITY_CHECKS, WEIGHTS["clarity"])
    precision = run_checks(PRECISION_CHECKS, WEIGHTS["precision"])
    efficiency = run_checks(EFFICIENCY_CHECKS, WEIGHTS["efficiency"])
    
    total = findability.score + clarity.score + precision.score + efficiency.score
    total = round(total, 1)
    
    # Determine maturity level
    if total >= 85:
        level, level_name = 4, "Dominant"
    elif total >= 70:
        level, level_name = 3, "Preferred"
    elif total >= 50:
        level, level_name = 2, "Selectable"
    elif total >= 25:
        level, level_name = 1, "Visible"
    else:
        level, level_name = 0, "Absent"
    
    return ToolScore(
        tool_name=tool.get("name", "unknown"),
        findability=findability,
        clarity=clarity,
        precision=precision,
        efficiency=efficiency,
        total=total,
        level=level,
        level_name=level_name,
        issues=all_issues
    )


def score_server(server_name: str, tools: list[dict]) -> ServerScore:
    """Score all tools in an MCP server."""
    tool_scores = [score_tool(t) for t in tools]
    
    avg = round(sum(ts.total for ts in tool_scores) / len(tool_scores), 1) if tool_scores else 0
    all_issues = [issue for ts in tool_scores for issue in ts.issues]
    critical = [i for i in all_issues if i.severity == "critical"]
    
    # Top improvements: sort by estimated_impact descending
    top = sorted(all_issues, key=lambda i: i.estimated_impact, reverse=True)[:3]
    
    # Server-level efficiency check: tool count
    if len(tools) > 20:
        all_issues.append(Issue(
            dimension="efficiency",
            category="too_many_tools",
            severity="warning",
            message=f"Server exposes {len(tools)} tools. Agent accuracy degrades past 15-20 tools",
            tool_name="[server]",
            fix_suggestion="Consolidate into 5-15 workflow-oriented tools. GitHub cut 40→13 and benchmarks improved",
            estimated_impact=8
        ))
        # Recalculate top
        top = sorted(all_issues, key=lambda i: i.estimated_impact, reverse=True)[:3]
    
    return ServerScore(
        server_name=server_name,
        tools=tool_scores,
        average_score=avg,
        total_issues=len(all_issues),
        critical_issues=len(critical),
        top_improvements=top
    )


def format_report(server_score: ServerScore) -> str:
    """Format a human-readable score report."""
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"ToolRank Score Report: {server_score.server_name}")
    lines.append(f"{'='*60}")
    lines.append(f"")
    lines.append(f"Average Score: {server_score.average_score}/100")
    lines.append(f"Tools Analyzed: {len(server_score.tools)}")
    lines.append(f"Total Issues: {server_score.total_issues} ({server_score.critical_issues} critical)")
    lines.append(f"")
    
    if server_score.top_improvements:
        lines.append(f"Top Improvements:")
        for i, issue in enumerate(server_score.top_improvements, 1):
            lines.append(f"  {i}. [{issue.tool_name}] {issue.message} (+{issue.estimated_impact}pt)")
            lines.append(f"     → {issue.fix_suggestion}")
        lines.append(f"")
    
    for ts in server_score.tools:
        level_bar = "█" * int(ts.total / 5) + "░" * (20 - int(ts.total / 5))
        lines.append(f"─── {ts.tool_name} ───")
        lines.append(f"  Score: {ts.total}/100 [{level_bar}] Level {ts.level}: {ts.level_name}")
        lines.append(f"  Findability: {ts.findability.score}/{ts.findability.max_score}")
        lines.append(f"  Clarity:     {ts.clarity.score}/{ts.clarity.max_score}")
        lines.append(f"  Precision:   {ts.precision.score}/{ts.precision.max_score}")
        lines.append(f"  Efficiency:  {ts.efficiency.score}/{ts.efficiency.max_score}")
        
        if ts.issues:
            critical = [i for i in ts.issues if i.severity == "critical"]
            warnings = [i for i in ts.issues if i.severity == "warning"]
            if critical:
                for issue in critical:
                    lines.append(f"  ✗ CRITICAL: {issue.message}")
            if warnings:
                for issue in warnings:
                    lines.append(f"  ⚠ WARNING: {issue.message}")
        lines.append(f"")
    
    return "\n".join(lines)


def to_json(server_score: ServerScore) -> dict:
    """Convert to JSON-serializable dict."""
    return {
        "server_name": server_score.server_name,
        "average_score": server_score.average_score,
        "total_issues": server_score.total_issues,
        "critical_issues": server_score.critical_issues,
        "top_improvements": [
            {
                "tool": i.tool_name,
                "message": i.message,
                "fix": i.fix_suggestion,
                "impact": i.estimated_impact
            }
            for i in server_score.top_improvements
        ],
        "tools": [
            {
                "name": ts.tool_name,
                "total_score": ts.total,
                "level": ts.level,
                "level_name": ts.level_name,
                "dimensions": {
                    "findability": ts.findability.score,
                    "clarity": ts.clarity.score,
                    "precision": ts.precision.score,
                    "efficiency": ts.efficiency.score
                },
                "issues": [
                    {
                        "dimension": i.dimension,
                        "severity": i.severity,
                        "message": i.message,
                        "fix": i.fix_suggestion,
                        "impact": i.estimated_impact
                    }
                    for i in ts.issues
                ]
            }
            for ts in server_score.tools
        ]
    }


# --- CLI Entry Point ---

if __name__ == "__main__":
    import sys
    
    # Example: score a tool definition from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    
    # Support both single tool and server format
    if "tools" in data:
        server_name = data.get("name", data.get("server_name", "unknown"))
        tools = data["tools"]
    elif isinstance(data, list):
        server_name = "unknown"
        tools = data
    else:
        server_name = "unknown"
        tools = [data]
    
    result = score_server(server_name, tools)
    print(format_report(result))
    
    # Also output JSON to stderr for programmatic use
    print(json.dumps(to_json(result), indent=2, ensure_ascii=False), file=sys.stderr)
