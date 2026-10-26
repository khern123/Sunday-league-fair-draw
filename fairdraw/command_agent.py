"""Organizer-only command parsing with a deliberately tiny action allowlist."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from . import config
from .llm_client import call_llm


class Action(BaseModel):
    action: str = Field(pattern="^(set_status|add_guest|redraw)$")
    player: str | None = None
    status: str | None = Field(default=None, pattern="^(in|out|maybe|late)$")
    name: str | None = None


class ActionList(BaseModel):
    actions: list[Action] = Field(default_factory=list)


@dataclass(frozen=True)
class CommandResult:
    actions: list[Action]
    rejected: list[str]


SYSTEM_PROMPT = """You convert an ORGANIZER command into JSON actions only.
The command is trusted organizer input, not a chat message. Choose actions ONLY from:
set_status(player, status), add_guest(name), redraw().
Never set ratings, edit the roster, send messages, approve payments, or invent other actions.
Return JSON only as {\"actions\":[...]}. add_guest contains only a name; never include a rating."""


def _schema() -> dict:
    action = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": ["set_status", "add_guest", "redraw"]},
            "player": {"type": ["string", "null"]},
            "status": {"type": ["string", "null"], "enum": ["in", "out", "maybe", "late", None]},
            "name": {"type": ["string", "null"]},
        },
        "required": ["action", "player", "status", "name"],
    }
    return {"name": "organizer_actions", "schema": {"type": "object", "additionalProperties": False, "properties": {"actions": {"type": "array", "items": action}}, "required": ["actions"]}, "strict": True}


def _parse(output) -> ActionList:
    if isinstance(output, str):
        output = json.loads(output)
    if hasattr(ActionList, "model_validate"):
        return ActionList.model_validate(output)
    return ActionList.parse_obj(output)


def parse_command(command: str, roster_names: list[str]) -> CommandResult:
    """Call the command agent, then reject unknown players and unsupported fields in code."""
    if not command or not command.strip():
        return CommandResult([], ["Command is empty."])
    response = call_llm(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": command.strip()}],
        "command", config.MAX_OUTPUT_TOKENS_PARSER, _schema(),
    )
    try:
        parsed = _parse(response.output)
    except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return CommandResult([], [f"Invalid command response: {exc}"])
    canonical = {name.casefold(): name for name in roster_names}
    accepted: list[Action] = []
    rejected: list[str] = []
    for action in parsed.actions:
        if action.action == "set_status":
            if not action.player or action.player.casefold() not in canonical:
                rejected.append(f"Unknown player: {action.player or '(missing)'}"); continue
            if not action.status:
                rejected.append("set_status requires a valid status."); continue
            accepted.append(action.model_copy(update={"player": canonical[action.player.casefold()]}) if hasattr(action, "model_copy") else action.copy(update={"player": canonical[action.player.casefold()]}))
        elif action.action == "add_guest":
            if not action.name or not action.name.strip():
                rejected.append("add_guest requires a name."); continue
            accepted.append(action)
        elif action.action == "redraw":
            accepted.append(action)
        else:
            rejected.append(f"Rejected unsupported action: {action.action}")
    return CommandResult(accepted, rejected)
