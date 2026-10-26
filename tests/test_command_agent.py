from types import SimpleNamespace

from fairdraw import command_agent


def fake_llm(monkeypatch, payload):
    monkeypatch.setattr(command_agent, "call_llm", lambda *args, **kwargs: SimpleNamespace(output=payload))


def test_valid_organizer_actions_are_allowlisted(monkeypatch):
    fake_llm(monkeypatch, {"actions": [{"action": "set_status", "player": "sam", "status": "late", "name": None}, {"action": "add_guest", "player": None, "status": None, "name": "Tom"}, {"action": "redraw", "player": None, "status": None, "name": None}]})
    result = command_agent.parse_command("mark Sam late, add Tom and redraw", ["Sam"])
    assert [action.action for action in result.actions] == ["set_status", "add_guest", "redraw"]
    assert result.actions[0].player == "Sam"
    assert result.actions[1].name == "Tom"


def test_rating_and_roster_edit_are_rejected(monkeypatch):
    fake_llm(monkeypatch, {"actions": [{"action": "set_rating", "player": "Sam", "status": None, "name": None}, {"action": "edit_roster", "player": None, "status": None, "name": "Sam"}]})
    result = command_agent.parse_command("set Sam's rating to 10 and edit the roster", ["Sam"])
    assert result.actions == []
    assert result.rejected


def test_unknown_player_is_rejected(monkeypatch):
    fake_llm(monkeypatch, {"actions": [{"action": "set_status", "player": "Ali", "status": "in", "name": None}]})
    result = command_agent.parse_command("Ali is in", ["Sam"])
    assert not result.actions and "Unknown player" in result.rejected[0]
