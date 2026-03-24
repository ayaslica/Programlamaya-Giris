from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings, get_settings
from app.models.schemas import RuleDebug


class RuleEngine:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.rules = self._load_rules()

    def _load_rules(self) -> list[dict]:
        path = Path(self.settings.rules["path"])
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def evaluate(self, context: dict[str, float]) -> tuple[float, list[RuleDebug], bool]:
        score = 0.0
        debug_rows: list[RuleDebug] = []
        mandatory_ok = True

        for rule in self.rules:
            local_vars = {k: v for k, v in context.items()}
            passed = bool(eval(rule["condition"], {"__builtins__": {}}, local_vars))
            contribution = rule["weight"] if passed else 0.0
            score += contribution

            if rule["type"] == "mandatory" and not passed:
                mandatory_ok = False

            debug_rows.append(
                RuleDebug(
                    name=rule["name"],
                    passed=passed,
                    score_contribution=contribution,
                    reason=rule["reason_pass"] if passed else rule["reason_fail"],
                    rule_type=rule["type"],
                )
            )

        return score, debug_rows, mandatory_ok
