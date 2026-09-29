"""构造有预算的 Planner 视图；原始 AgentContext 历史保持不变。"""
from copy import deepcopy
import json
import re


def _query_shape(query):
    # 仅用于保守识别表别名修正，不参与 SQL 执行或安全校验。
    return re.sub(r"\s+", " ", re.sub(r"\b\w+\.", "", query)).strip().lower()


def planner_context(context, budget=20000):
    raw = context.to_dict()
    events = raw["history"]
    actions = {e["action_id"]: e for e in events if e["type"] == "action"}
    observations = {e["action_id"]: e for e in events if e["type"] == "observation" and e["action_id"] is not None}
    latest_iteration = max((e["iteration"] for e in events), default=0)
    view = {"user_query": raw["user_query"][:4000], "plan": raw["plan"][:10],
            "iteration": raw["iteration"], "findings": raw["findings"][-10:],
            "history": [], "history_summary": [], "evidence": []}
    schemas = [e for e in events if e["type"] == "observation" and e["data"].get("kind") == "compact_schema"]
    if schemas:
        view["schema"] = deepcopy(schemas[-1]["data"])
    for event in events:
        data = event["data"]
        aid = event["action_id"]
        if event["type"] == "observation" and data.get("kind") == "compact_schema":
            continue
        if event["iteration"] == latest_iteration:
            view["history"].append(deepcopy(event))
            continue
        if event["type"] == "action":
            observation = observations.get(aid, {}).get("data", {})
            summary = {"action_id": aid, "tool": data.get("action"), "status": observation.get("status", "no_observation")}
            if observation.get("kind") == "compact_schema":
                summary["result"] = "schema available separately"
            elif observation.get("status") == "error":
                summary["error"] = observation.get("error", {})
                shape = _query_shape(data.get("arguments", {}).get("query", ""))
                fixes = [other_id for other_id, other in actions.items() if other_id > aid
                         and observations.get(other_id, {}).get("data", {}).get("status") == "ok"
                         and other["data"].get("action") == "run_sql" and shape
                         and _query_shape(other["data"].get("arguments", {}).get("query", "")) == shape]
                if fixes:
                    summary["resolved_by_action"] = min(fixes)
            else:
                summary["columns"] = observation.get("columns", [])
            view["history_summary"].append(summary)
        elif data.get("status") == "ok":
            # 不把可验证数值改写为 LLM 摘要，保留旧业务证据与来源引用。
            view["evidence"].append({"action_id": aid, "data": deepcopy(data)})
        elif aid is None:
            view["history_summary"].append({"iteration": event["iteration"], "error": data.get("error")})
    view["history_omitted"] = len(events) - len(view["history"])
    size = lambda: len(json.dumps(view, ensure_ascii=False))
    # 首先移除低价值摘要；随后才裁减旧证据，并显式报告损失。
    while size() > budget and view["history_summary"]:
        view["history_summary"].pop(0)
        view["summaries_omitted"] = view.get("summaries_omitted", 0) + 1
    while size() > budget and view["evidence"]:
        view["evidence"].pop(0)
        view["evidence_omitted"] = view.get("evidence_omitted", 0) + 1
        view["truncated"] = True
    while size() > budget and len(view["history"]) > 2:
        view["history"].pop(0)
        view["history_omitted"] += 1
        view["truncated"] = True
    while size() > budget and view["findings"]:
        view["findings"].pop(0)
        view["findings_omitted"] = view.get("findings_omitted", 0) + 1
        view["truncated"] = True
    return view
