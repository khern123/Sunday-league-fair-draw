"""Load the course-supported API configuration without exposing secrets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


DEFAULT_OPENAI_MODEL = "gpt-6-luna"


@dataclass(frozen=True)
class KeyState:
    """Safe-to-display API configuration state."""

    key_name: str | None
    api_key: str | None
    model: str | None
    env_path: Path | None
    message: str

    @property
    def available(self) -> bool:
        return self.api_key is not None


def _candidate_paths(repo_root: Path) -> tuple[Path, Path]:
    return repo_root / ".env", repo_root.parent / ".env"


def load_key_state(repo_root: str | Path | None = None) -> KeyState:
    """Find the first allowed ``.env`` and read only the two allowed keys.

    ``repo_root`` should be the directory containing ``app.py``. When omitted,
    it is inferred from this module's project location.
    """

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    env_path = next((path for path in _candidate_paths(root) if path.is_file()), None)

    if env_path is None:
        return KeyState(
            key_name=None,
            api_key=None,
            model=None,
            env_path=None,
            message=(
                "No API key found. Put a .env file in either the repository root "
                f"({root}) or its parent ({root.parent}), using only "
                "PORTKEY_API_KEY or OPENAI_API_KEY."
            ),
        )

    values = dotenv_values(env_path)
    portkey_key = values.get("PORTKEY_API_KEY")
    openai_key = values.get("OPENAI_API_KEY")

    if portkey_key:
        return KeyState("PORTKEY_API_KEY", portkey_key, "gpt-6-luna", env_path, "API key loaded.")
    if openai_key:
        return KeyState("OPENAI_API_KEY", openai_key, DEFAULT_OPENAI_MODEL, env_path, "API key loaded.")

    return KeyState(
        key_name=None,
        api_key=None,
        model=None,
        env_path=env_path,
        message=(
            f"No API key found in {env_path}. Add PORTKEY_API_KEY or OPENAI_API_KEY "
            "to a .env file in the repository root or its parent."
        ),
    )


def describe_key_source(state: KeyState | None = None, repo_root: str | Path | None = None) -> str:
    """Return a safe, masked description suitable for UI display."""

    state = state or load_key_state(repo_root)
    if not state.available or state.key_name is None or state.env_path is None:
        return "No key found"
    return f"{state.key_name} loaded from {state.env_path} (value hidden)"
