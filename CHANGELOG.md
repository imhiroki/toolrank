# ToolRank Score Changelog

All notable changes to the scoring methodology are documented here.

## [1.0.0] - 2026-03-29

### Initial Release
- 14 rule-based checks across 4 dimensions
- Findability (25%): name quality, keyword overlap, naming convention
- Clarity (35%): description length, action verb, usage context, return value, name-desc alignment
- Precision (25%): schema presence, types, param descriptions, required fields, enums/defaults
- Efficiency (15%): token count, tool count
- Dynamic weights loaded from weights.json
- Calibration via calibrate.py (useCount correlation)

### Data
- Initial scan: 4,162 servers, 1,122 scored
- Average score: 84.7/100
- Distribution: 677 Dominant, 406 Preferred, 39 Selectable

### Validation
- Selection simulation (local, 500 rounds): r=0.828 correlation between score and selection rate
- High-quality tools (95+ score) selected 85.4% of the time vs 1.8% for low-quality (59 score)
