# ToolRank Governance

## Principles

1. **Transparency**: Scoring logic is open source and auditable
2. **Reproducibility**: Same input always produces same score (Level A)
3. **Versioning**: Every scoring logic change is versioned and documented
4. **Neutrality**: No preferential treatment for any server or organization

## Score Versioning

ToolRank Score uses semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Fundamental scoring methodology change (dimension weights, new dimensions)
- **MINOR**: New checks added or existing checks modified
- **PATCH**: Bug fixes that don't change scoring behavior

All changes are documented in [CHANGELOG.md](CHANGELOG.md).

## How Scores Are Calculated

Level A (free, deterministic):
- 14 rule-based checks across 4 dimensions
- Weights loaded from `weights.json` (auto-calibrated weekly)
- Source: [packages/scoring/toolrank_score.py](packages/scoring/toolrank_score.py)

Level C (Pro, AI-assisted):
- Claude API semantic analysis
- Requires API key, costs per call
- Source: [packages/scoring/level_c_score.py](packages/scoring/level_c_score.py)

## Weight Calibration

Dimension weights are calibrated automatically via `calibrate.py`:
- Analyzes correlation between dimension scores and real-world usage (useCount)
- Runs weekly via GitHub Actions
- Changes applied only with `--apply` flag
- All weight changes logged in `weights.json` with timestamp

## Data Sources

Current:
- Smithery Registry API (registry.smithery.ai)
- Official MCP Registry (registry.modelcontextprotocol.io)

Planned:
- MCP.so
- PulseMCP
- SkillsIndex

## Dispute Resolution

If you believe your server's score is inaccurate:

1. **Check the score page**: [toolrank.dev/score](https://toolrank.dev/score) shows specific issues
2. **Open a GitHub Issue**: [github.com/imhiroki/toolrank/issues](https://github.com/imhiroki/toolrank/issues)
3. **Include your tool definition JSON** for reproducibility
4. **Response time**: Issues are reviewed within 7 days

## Future: Advisory Board

As ToolRank grows, we plan to establish an advisory board of 3-5 MCP ecosystem participants to:
- Review major scoring methodology changes before release
- Provide input on weight calibration
- Ensure neutrality and fairness

## Contact

- GitHub: [@imhiroki](https://github.com/imhiroki)
- Website: [toolrank.dev](https://toolrank.dev)
