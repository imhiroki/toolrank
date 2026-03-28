"""
ToolRank Weight Calibrator v0.1
Analyzes correlation between useCount (actual agent selection) and ToolRank Score dimensions.
Recommends weight adjustments to align scoring with real-world selection behavior.

Runs weekly after full scan. Outputs recommendations for weight updates.

Usage:
  python calibrate.py                    # Analyze latest scan data
  python calibrate.py --apply            # Auto-update weights (Phase 2)
"""

import json
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("calibrator")

DATA_DIR = Path(__file__).parent / "data"


def load_scores() -> list[dict]:
    """Load latest scores with useCount data."""
    latest = DATA_DIR / "latest_scores.json"
    if not latest.exists():
        log.error("No scan data found. Run scanner first.")
        return []
    with open(latest) as f:
        return json.load(f)


def pearson_correlation(x: list[float], y: list[float]) -> float:
    """Calculate Pearson correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0.0
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
    
    if den_x == 0 or den_y == 0:
        return 0.0
    
    return num / (den_x * den_y)


def analyze(scores: list[dict]) -> dict:
    """Analyze correlation between useCount and score dimensions."""
    # Filter servers with useCount data
    with_usage = [s for s in scores if s.get("use_count", 0) > 0]
    
    if len(with_usage) < 10:
        log.warning(f"Only {len(with_usage)} servers with useCount data. Need 10+ for meaningful analysis.")
        return {}
    
    log.info(f"Analyzing {len(with_usage)} servers with usage data")
    
    # Extract dimensions
    use_counts = [s["use_count"] for s in with_usage]
    # Log-transform useCount (it's very skewed)
    import math
    log_usage = [math.log(u + 1) for u in use_counts]
    
    # Get dimension scores from each tool's average
    findability = []
    clarity = []
    precision = []
    efficiency = []
    total = []
    
    for s in with_usage:
        tools = s.get("tools", [])
        if not tools:
            continue
        
        f_avg = sum(t["dimensions"]["findability"] for t in tools) / len(tools)
        c_avg = sum(t["dimensions"]["clarity"] for t in tools) / len(tools)
        p_avg = sum(t["dimensions"]["precision"] for t in tools) / len(tools)
        e_avg = sum(t["dimensions"]["efficiency"] for t in tools) / len(tools)
        
        findability.append(f_avg)
        clarity.append(c_avg)
        precision.append(p_avg)
        efficiency.append(e_avg)
        total.append(s["average_score"])
    
    if len(findability) < 10:
        return {}
    
    # Calculate correlations
    correlations = {
        "findability": round(pearson_correlation(log_usage[:len(findability)], findability), 3),
        "clarity": round(pearson_correlation(log_usage[:len(clarity)], clarity), 3),
        "precision": round(pearson_correlation(log_usage[:len(precision)], precision), 3),
        "efficiency": round(pearson_correlation(log_usage[:len(efficiency)], efficiency), 3),
        "total_score": round(pearson_correlation(log_usage[:len(total)], total), 3),
    }
    
    # Current weights
    current_weights = {
        "findability": 25,
        "clarity": 35,
        "precision": 25,
        "efficiency": 15,
    }
    
    # Calculate recommended weights based on correlation strength
    dims = ["findability", "clarity", "precision", "efficiency"]
    abs_corrs = {d: abs(correlations[d]) for d in dims}
    total_corr = sum(abs_corrs.values())
    
    if total_corr > 0:
        recommended_weights = {
            d: round(abs_corrs[d] / total_corr * 100)
            for d in dims
        }
        # Normalize to 100
        diff = 100 - sum(recommended_weights.values())
        recommended_weights["clarity"] += diff  # Add remainder to clarity
    else:
        recommended_weights = current_weights.copy()
    
    # Generate report
    report = {
        "date": datetime.now().isoformat(),
        "sample_size": len(findability),
        "correlations": correlations,
        "current_weights": current_weights,
        "recommended_weights": recommended_weights,
        "weight_changes": {
            d: recommended_weights[d] - current_weights[d]
            for d in dims
        },
        "interpretation": [],
    }
    
    # Interpret results
    for dim in dims:
        corr = correlations[dim]
        change = report["weight_changes"][dim]
        if abs(corr) > 0.3:
            strength = "strong" if abs(corr) > 0.5 else "moderate"
            direction = "positive" if corr > 0 else "negative"
            report["interpretation"].append(
                f"{dim}: {strength} {direction} correlation ({corr}). "
                f"Weight change: {'+' if change > 0 else ''}{change}%"
            )
        else:
            report["interpretation"].append(
                f"{dim}: weak correlation ({corr}). Consider reviewing scoring criteria."
            )
    
    return report


def main():
    parser = argparse.ArgumentParser(description="ToolRank Weight Calibrator")
    parser.add_argument("--apply", action="store_true", help="Auto-update weights (Phase 2)")
    args = parser.parse_args()
    
    scores = load_scores()
    if not scores:
        return
    
    report = analyze(scores)
    if not report:
        log.error("Insufficient data for analysis")
        return
    
    # Print report
    print("\n" + "=" * 60)
    print("ToolRank Weight Calibration Report")
    print("=" * 60)
    print(f"Date: {report['date']}")
    print(f"Sample size: {report['sample_size']} servers with usage data")
    print()
    
    print("Correlations (useCount vs dimension score):")
    for dim, corr in report["correlations"].items():
        bar_len = int(abs(corr) * 20)
        bar = ("+" if corr > 0 else "-") * bar_len
        print(f"  {dim:15s}: {corr:+.3f} [{bar:20s}]")
    print()
    
    print("Weight Recommendations:")
    print(f"  {'Dimension':15s} {'Current':>8s} {'Recommended':>12s} {'Change':>8s}")
    for dim in ["findability", "clarity", "precision", "efficiency"]:
        curr = report["current_weights"][dim]
        rec = report["recommended_weights"][dim]
        change = report["weight_changes"][dim]
        arrow = "→" if change == 0 else ("↑" if change > 0 else "↓")
        print(f"  {dim:15s} {curr:7d}% {rec:11d}% {arrow}{abs(change):+d}%")
    print()
    
    print("Interpretation:")
    for line in report["interpretation"]:
        print(f"  • {line}")
    
    # Save report
    report_file = DATA_DIR / f"calibration_{datetime.now().strftime('%Y%m%d')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {report_file}")
    
    if args.apply:
        log.warning("Auto-apply is Phase 2. For now, review and manually update weights in toolrank_score.py")


if __name__ == "__main__":
    main()
