"""Fail-closed repository hygiene scan."""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[3]  # AI Foundations
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,})")
ENV_SECRET = re.compile(r"(?:PORTKEY|OPENAI)_API_KEY\s*=\s*(?!your_key_here\s*$|$)[^\s#]+", re.M)

def main() -> int:
    findings: list[str] = []
    username = Path.home().name.casefold()
    skip = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
    for path in WORKSPACE.rglob("*"):
        if not path.is_file() or any(part in skip or part.startswith(".pytest-run") for part in path.parts):
            continue
        relative = path.relative_to(WORKSPACE).as_posix()
        lowered = relative.casefold()
        if "/data/real/" in f"/{lowered}" or lowered.endswith("/data/real") or "/photos/" in f"/{lowered}" or lowered.endswith("/photos") or lowered.endswith("/results/cache.json"):
            findings.append(f"private/ignored path present: {relative}")
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        pattern = ENV_SECRET if path.name == ".env" else SECRET
        populated = any(re.match(r"^\s*(?:PORTKEY|OPENAI)_API_KEY\s*=\s*[^#\s]+", line) for line in text.splitlines()) if path.name == ".env" else bool(pattern.search(text))
        if populated:
            findings.append(f"secret-like value in working tree: {relative}")

    repositories = [p.parent for p in WORKSPACE.rglob(".git") if p.is_dir()]
    for repository in repositories:
        try:
            history = subprocess.run(
                ["git", "-C", str(repository), "log", "--all", "--full-history", "-G",
                 r"sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,}|(PORTKEY|OPENAI)_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]#]+",
                 "--format=%H", "--", "."], capture_output=True, text=True, check=False)
            if history.stdout.strip():
                findings.append(f"secret-like text in Git history: {repository}")
            tracked = subprocess.run(["git", "-C", str(repository), "ls-files", "-z"], capture_output=True, text=True, check=False)
            for item in tracked.stdout.split("\0"):
                if username and re.search(rf"(?:[A-Za-z]:[\\/]+Users[\\/]+){re.escape(username)}(?:[\\/]|$)", item, re.I):
                    findings.append(f"Windows username path in tracked filename: {repository / item}")
        except OSError as exc:
            findings.append(f"Git scan failed for {repository}: {exc}")

    if findings:
        print("SECRET CHECK FAILED")
        print("\n".join(dict.fromkeys(findings)))
        return 1
    print("SECRET CHECK PASSED: no secret-like values, populated .env, private paths, or username paths found.")
    print(f"Git history repositories scanned under {WORKSPACE}: {len(repositories)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
