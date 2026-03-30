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
2. **Open a GitHub Issue** using the [Score Dispute template](https://github.com/imhiroki/toolrank/issues/new?template=score-dispute.md)
3. **Include**: server name, expected score, actual score, and your tool definition JSON
4. **Response time**: Issues are reviewed within 7 days
5. **Outcome**: If the dispute is valid, score logic is patched and a CHANGELOG entry is added

## Change Notice Policy

**MAJOR changes** (weight restructure, new dimensions, methodology shifts):
- Announced via GitHub Discussion at least **14 days** before release
- Include: rationale, before/after impact analysis, and migration guidance
- Existing scores are re-calculated and diff published

**MINOR changes** (new checks, threshold adjustments):
- Announced via CHANGELOG at time of release
- Include: what changed, which servers are affected, and expected score impact

**Weight calibration** (weekly auto-updates):
- All weight changes logged in `weights.json` with timestamp
- If any single weight changes by >5 points, a GitHub Discussion is opened explaining why

## External Review

**Current state**: ToolRank is maintained by a single developer ([@imhiroki](https://github.com/imhiroki)).

**Advisory board criteria** (to be established when GitHub Stars reach 50+):
- 3-5 participants from the MCP ecosystem (server developers, registry operators, framework maintainers)
- Required review for MAJOR version changes
- Quarterly scoring methodology review
- Public meeting notes

**How to become a reviewer**: Open a GitHub Issue expressing interest. Requirements: active MCP server developer or ecosystem contributor.

## Contact

- GitHub: [@imhiroki](https://github.com/imhiroki)
- Website: [toolrank.dev](https://toolrank.dev)
