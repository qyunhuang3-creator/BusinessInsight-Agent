"""当前任务的紧凑上下文，不持有完整 CSV 或 SQL 明细结果。"""

from copy import deepcopy
from dataclasses import dataclass, field
import json
from src.schema_summary import schema_summary

OBSERVATION_CHAR_BUDGET = 6000


def compact_observation(observation):
    """小型表格最多30行；大型结果仍只留5行。容量不代表聚合语义。"""
    if isinstance(observation.get("tables"), list) and all(
            isinstance(t, dict) and "table_name" in t and "columns" in t
            for t in observation["tables"]):
        return schema_summary(observation, OBSERVATION_CHAR_BUDGET)
    result = _compact(observation)
    rows = observation.get("rows")
    if isinstance(rows, list):
        compact_table = (len(rows) <= 30 and isinstance(observation.get("columns"), list)
                         and len(observation["columns"]) <= 15
                         and len(json.dumps(rows, ensure_ascii=False)) <= 5000)
        limit = 30 if compact_table else 5
        result["rows"] = [_compact(row) for row in rows[:limit]]
        result.pop("rows_context_omitted", None)
        changed = result["rows"] != rows
        while result["rows"] and len(json.dumps(result, ensure_ascii=False)) > OBSERVATION_CHAR_BUDGET - 200:
            result["rows"].pop()
            changed = True
        if len(result["rows"]) < len(rows):
            result["rows_context_omitted"] = len(rows) - len(result["rows"])
        result["truncated"] = bool(observation.get("truncated")) or changed
        if changed:
            result["context_truncated"] = True
    if len(json.dumps(result, ensure_ascii=False)) > OBSERVATION_CHAR_BUDGET:
        # 非表格的超大 Observation 也不能突破总预算。
        result = {"status": observation.get("status"), "truncated": True,
                  "context_truncated": True, "preview": json.dumps(result, ensure_ascii=False)[:2500]}
    return result


def _compact(value, key="", depth=0):
    """有界副本：SQL 行最多 5 行，其他列表最多 30 项，文本最多 2000 字。"""
    if depth > 8:
        return "[context depth limit]"
    if isinstance(value, dict):
        result = {str(k): _compact(v, str(k), depth + 1) for k, v in list(value.items())[:50]}
        for k, v in value.items():
            if isinstance(v, list) and len(v) > (5 if k == "rows" else 30):
                result[f"{k}_context_omitted"] = len(v) - (5 if k == "rows" else 30)
        if len(value) > 50:
            result["context_keys_omitted"] = len(value) - 50
        return result
    if isinstance(value, (list, tuple)):
        return [_compact(v, depth=depth + 1) for v in value[:5 if key == "rows" else 30]]
    if isinstance(value, str):
        return value if len(value) <= 2000 else value[:2000] + "...[context text truncated]"
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return f"[unsupported {type(value).__name__}]"


@dataclass
class AgentContext:
    user_query: str
    plan: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    iteration: int = 0

    def set_plan(self, steps):
        self.plan = _compact(steps)

    def add_action(self, action):
        action_id = 1 + sum(event["type"] == "action" for event in self.history)
        self.history.append({"type": "action", "iteration": self.iteration,
                             "action_id": action_id, "data": _compact(action)})
        return action_id

    def add_observation(self, observation, action_id=None):
        event = {"type": "observation", "iteration": self.iteration,
                 "action_id": action_id, "data": compact_observation(observation)}
        self.history.append(event)
        return deepcopy(event)

    def add_finding(self, statement, evidence_action_id):
        """事实必须引用成功的工具 Observation；语义验证由 Planner 负责。"""
        if not any(e["type"] == "observation" and e["action_id"] == evidence_action_id
                   and e["data"].get("status") == "ok" for e in self.history):
            raise ValueError("finding 必须引用成功的 Observation")
        finding = {"statement": _compact(statement), "evidence_action_id": evidence_action_id}
        if finding not in self.findings:
            self.findings.append(finding)

    def latest_observation(self):
        return next((deepcopy(e) for e in reversed(self.history) if e["type"] == "observation"), None)

    def to_dict(self):
        return deepcopy({"user_query": self.user_query, "plan": self.plan,
                         "history": self.history, "findings": self.findings,
                         "iteration": self.iteration})
