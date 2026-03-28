"""Test the scoring engine with good/bad/medium examples."""
import json
import sys
sys.path.insert(0, ".")
from toolrank_score import score_server, format_report, to_json

with open("test_data.json") as f:
    data = json.load(f)

for key in ["good_server", "bad_server", "medium_server"]:
    server = data[key]
    result = score_server(server["name"], server["tools"])
    print(format_report(result))
    print()
