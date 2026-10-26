"""Scale only completed, real token measurements."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NIGHTS_PER_LEAGUE_MONTH = 4
CACHE_FRACTIONS = (0.0, 0.5)

def main():
    path = ROOT / "results/token_runs.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    lines = ["# Scale cost report", "", "## Editable assumptions", f"- Nights per league per month: `{NIGHTS_PER_LEAGUE_MONTH}`", "- One attendance parse plus one announcement per night.", "- Cache fractions tested: `0.0` and `0.5`.", "- The draw engine itself uses zero tokens.", ""]
    if data.get("status") != "completed" or not data.get("statistics"):
        lines += ["**No scale table produced:** real token measurements are unavailable.", f"- {data.get('reason', 'results/token_runs.json is missing completed real measurements')}", "- No token totals or prices were invented.", ""]
    else:
        mean = data["statistics"]
        required = {"input_tokens", "cached_input_tokens", "output_tokens"}
        if not required.issubset(mean):
            lines += ["**No scale table produced:** required token fields are missing.", "- No token totals or prices were invented.", ""]
        else:
            uncached_input = mean["input_tokens"]["mean"]; cached_input = mean["cached_input_tokens"]["mean"]; output = mean["output_tokens"]["mean"]
            lines += ["| Cache fraction | Tokens/night | Tokens/league/month | 1 league/month | 100 leagues/month | 10,000 leagues/month | Cost/night |", "|---:|---:|---:|---:|---:|---:|---:|"]
            for fraction in CACHE_FRACTIONS:
                tokens = uncached_input * (1 - fraction) + cached_input * fraction + output; monthly = tokens * NIGHTS_PER_LEAGUE_MONTH
                lines.append(f"| {fraction:.0%} | {tokens:.2f} | {monthly:.2f} | {monthly:.2f} | {monthly*100:.2f} | {monthly*10000:.2f} | prices not set |")
            lines += ["", "prices not set; fill config.PRICING from course materials"]
    out = ROOT / "results/scale_costs.md"; out.write_text("\n".join(lines) + "\n", encoding="utf-8"); print("\n".join(lines))

if __name__ == "__main__": main()
