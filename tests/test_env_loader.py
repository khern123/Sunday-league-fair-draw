from pathlib import Path

from fairdraw.env_loader import describe_key_source, load_key_state


def write_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_env_in_repo_root_is_found(tmp_path: Path) -> None:
    write_env(tmp_path / ".env", "PORTKEY_API_KEY=root-secret\n")
    state = load_key_state(tmp_path)
    assert state.key_name == "PORTKEY_API_KEY"
    assert state.api_key == "root-secret"
    assert state.env_path == tmp_path / ".env"


def test_env_only_in_parent_is_found(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    write_env(tmp_path / ".env", "OPENAI_API_KEY=parent-secret\n")
    state = load_key_state(repo)
    assert state.key_name == "OPENAI_API_KEY"
    assert state.api_key == "parent-secret"
    assert state.env_path == tmp_path / ".env"


def test_repo_root_wins_when_both_exist(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    write_env(repo / ".env", "PORTKEY_API_KEY=root-secret\n")
    write_env(tmp_path / ".env", "OPENAI_API_KEY=parent-secret\n")
    state = load_key_state(repo)
    assert state.key_name == "PORTKEY_API_KEY"
    assert state.env_path == repo / ".env"


def test_missing_env_returns_no_key_state(tmp_path: Path) -> None:
    state = load_key_state(tmp_path)
    assert not state.available
    assert describe_key_source(state) == "No key found"
    assert "PORTKEY_API_KEY" in state.message
    assert "OPENAI_API_KEY" in state.message


def test_key_values_never_appear_in_messages(tmp_path: Path) -> None:
    secret = "super-secret-value"
    write_env(tmp_path / ".env", f"PORTKEY_API_KEY={secret}\n")
    state = load_key_state(tmp_path)
    assert secret not in state.message
    assert secret not in describe_key_source(state)
