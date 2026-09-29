"""Evidence-first report output layer. No database, Ground Truth or API imports.

Sources are supplied by the caller, not discovered by this module. Validation
proves equality to those sources, not the truth of their business semantics.
The optional LLM may order references only; it cannot write new factual prose.
"""
from copy import deepcopy
import html
import json
import math
import re

SECTIONS = ("anomaly_overview", "metric_decomposition", "dimension_attribution", "drill_down_findings")
FIELDS = ("executive_summary", *SECTIONS, "evidence", "hypotheses", "limitations", "recommended_next_checks")
HEADINGS = {
    "executive_summary": "Executive Summary", "anomaly_overview": "Anomaly Overview",
    "metric_decomposition": "Metric Decomposition", "dimension_attribution": "Dimension Attribution",
    "drill_down_findings": "Drill-down Findings", "evidence": "Evidence",
    "hypotheses": "Hypotheses（待验证）", "limitations": "Limitations",
    "recommended_next_checks": "Recommended Next Checks（不是已验证结论）",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _scalar(value):
    return (value is None or type(value) in (str, bool, int)
            or type(value) is float and math.isfinite(value))


def _lookup(data, path):
    _require(isinstance(path, list), "source path must be a list")
    for key in path:
        if isinstance(data, list):
            _require(type(key) is int and 0 <= key < len(data), "source row unavailable")
        else:
            _require(isinstance(data, dict) and isinstance(key, str) and key in data, "source field unavailable")
        data = data[key]
    return data


def sources_from_context(context):
    """Extract only successful observations, keeping action_id/query provenance.

    Caller supplies explicit field mappings; no answer parsing or LLM inference.
    Rows omitted by Context cannot be referenced or recovered here.
    """
    raw = context.to_dict() if hasattr(context, "to_dict") else context
    actions = {e["action_id"]: e["data"] for e in raw["history"] if e["type"] == "action"}
    result = {}
    for e in raw["history"]:
        if e["type"] != "observation" or e["data"].get("status") != "ok":
            continue
        aid = e.get("action_id")
        action = actions.get(aid, {})
        if action.get("action") not in ("run_sql", "inspect_data"):
            continue
        result[f"action_{aid}"] = {"status": "ok", "tool": action["action"],
            "reference": f"action_id={aid}", "query": action.get("arguments", {}).get("query"),
            "data": deepcopy(e["data"])}
    return result


def validate_evidence(bundle):
    _require(isinstance(bundle, dict), "report input must be an object")
    for key in ("question", "analysis_status", "origin"):
        _require(isinstance(bundle.get(key), str) and bool(bundle[key].strip()), "missing report metadata")
    sources, evidence = bundle.get("sources"), bundle.get("evidence")
    _require(isinstance(sources, dict) and isinstance(evidence, list), "missing sources/evidence")
    seen = set()
    for item in evidence:
        _require(isinstance(item, dict), "invalid evidence record")
        eid = item.get("id")
        _require(isinstance(eid, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", eid) and eid not in seen, "invalid/duplicate evidence id")
        seen.add(eid)
        _require(item.get("section") in SECTIONS and isinstance(item.get("metric"), str), "invalid evidence classification")
        _require(isinstance(item.get("period"), str) and isinstance(item.get("dimension"), str), "missing evidence scope")
        source = sources.get(item.get("source_id"), {})
        _require(isinstance(source, dict) and source.get("status") == "ok" and source.get("tool") in ("run_sql", "inspect_data", "deterministic_python"), "unsuccessful evidence source")
        _require(isinstance(source.get("reference"), str) and bool(source["reference"]), "missing source reference")
        values, refs = item.get("values"), item.get("references")
        _require(isinstance(values, dict) and bool(values) and isinstance(refs, dict) and set(values) == set(refs), "every value requires a source path")
        summary_fields = item.get("summary_fields", list(values))
        _require(isinstance(summary_fields, list) and bool(summary_fields)
                 and all(isinstance(k, str) and k in values for k in summary_fields), "invalid summary field")
        for name, value in values.items():
            _require(isinstance(name, str) and _scalar(value), "evidence values must be finite scalars")
            source_value = _lookup(source.get("data"), refs[name])
            _require(type(source_value) is type(value) and source_value == value, "evidence value differs from source")
    for key in ("hypotheses", "limitations", "recommended_next_checks"):
        items = bundle.get(key)
        _require(isinstance(items, dict) and all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in items.items()), "invalid narrative catalog")
    return bundle


def baseline_report(bundle):
    """Only references: rendering always resolves values from validated input."""
    ids = [e["id"] for e in bundle["evidence"]]
    return {"executive_summary": ids[:1] + [e["id"] for e in bundle["evidence"]
            if e["section"] in ("metric_decomposition", "dimension_attribution") and e["id"] not in ids[:1]],
            **{s: [e["id"] for e in bundle["evidence"] if e["section"] == s] for s in SECTIONS},
            "evidence": ids,
            **{s: list(bundle[s]) for s in ("hypotheses", "limitations", "recommended_next_checks")}}


def report_schema(bundle):
    """JSON Schema passed to the existing request_json client when explicitly injected."""
    base = baseline_report(bundle)
    properties = {}
    for field in FIELDS:
        allowed = list(base["evidence"] if field == "executive_summary" else base[field])
        properties[field] = {"type": "array", "items": {"type": "string", **({"enum": allowed} if allowed else {})},
                             "uniqueItems": True, "minItems": (1 if allowed else 0) if field == "executive_summary" else len(allowed),
                             "maxItems": len(allowed)}
    return {"type": "object", "additionalProperties": False, "required": list(FIELDS), "properties": properties}


def validate_report(value, schema):
    """Validate the complete deliberately small schema dialect above, without deps."""
    _require(isinstance(value, dict) and set(value) == set(schema["required"]), "report fields invalid")
    for name, spec in schema["properties"].items():
        entries = value[name]
        _require(isinstance(entries, list) and all(isinstance(x, str) for x in entries), "expected reference array")
        _require(spec["minItems"] <= len(entries) <= spec["maxItems"] and len(set(entries)) == len(entries), "missing/duplicate references")
        _require(all(x in spec["items"].get("enum", []) for x in entries), "unverified reference or narrative")


def _text(value):
    text = html.escape(str(value), quote=False).replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\`*_{\[\]}()#+!|>~])", r"\\\1", text)


def render_markdown(bundle, report, mode, fallback_reason=None):
    records = {e["id"]: e for e in bundle["evidence"]}
    lines = ["# Final Business Report", "", f"业务问题：{_text(bundle['question'])}", "",
             f"分析状态：{_text(bundle['analysis_status'])}；来源：{_text(bundle['origin'])}", "",
             f"报告模式：{mode}" + (f"；降级原因：{fallback_reason}" if fallback_reason else ""), "",
             "报告仅呈现输入证据；生成成功不等于分析任务已完成。数值保持输入精度，百分数单位以字段名为准。", ""]
    for section in FIELDS:
        lines.extend([f"## {HEADINGS[section]}", ""])
        if section == "hypotheses":
            lines.extend(["以下均为待验证解释，不属于 Evidence；报告生成器不能自动验证因果关系。", ""])
        if not report[section]:
            lines.extend(["未提供已验证证据或相关说明；不补造结论。", ""])
        for ref in report[section]:
            if section in ("hypotheses", "limitations", "recommended_next_checks"):
                lines.extend([f"- {_text(bundle[section][ref])}", ""])
                continue
            e = records[ref]
            if section == "executive_summary":
                facts = "；".join(f"{_text(k)}={_text(e['values'][k])}" for k in e.get("summary_fields", e["values"]))
                lines.extend([f"- **{_text(e['metric'])}**：{facts}。[{ref}]", ""])
                continue
            lines.extend([f"### {_text(e['metric'])} [{ref}]", "",
                          f"期间：{_text(e['period'])}；维度/路径：{_text(e['dimension'])}", "",
                          "| 字段 | 值 |", "|---|---:|"])
            for name, value in e["values"].items():
                lines.append(f"| {_text(name)} | {_text('未定义' if value is None else value)} |")
            lines.append("")
            if section == "evidence":
                source = bundle["sources"][e["source_id"]]
                lines.extend([f"来源：{_text(source['tool'])} / {_text(source['reference'])}", "",
                    f"字段引用：{_text(json.dumps(e['references'], ensure_ascii=False))}", ""])
                if source.get("query"):
                    lines.extend([f"SQL/计算引用：{_text(source['query'])}", ""])
    return "\n".join(lines)


def generate_report(bundle, client=None):
    """Default is entirely offline. Optional client called once, no retry.

    Invalid input evidence is rejected (never laundered via fallback). LLM/API
    errors instead fall back to ALL valid evidence. No exception text is logged.
    """
    try:
        bundle = deepcopy(validate_evidence(bundle))
    except (ValueError, TypeError, KeyError):
        return {"status": "error", "error": {"code": "invalid_evidence", "message": "证据缺少有效来源或与来源不一致"}}
    report, mode, reason, calls = baseline_report(bundle), "deterministic", None, 0
    schema = report_schema(bundle)
    if client is not None:
        mode = "deterministic_fallback"
        try:
            calls = 1
            response = client([{"role": "system", "content": "组织报告已有引用。只返回Schema对象，不写新文字、数字、因果解释；保留所有章节证据。"},
                {"role": "user", "content": json.dumps({"question": bundle["question"], "evidence": bundle["evidence"],
                    **{k: bundle[k] for k in ("hypotheses", "limitations", "recommended_next_checks")}}, ensure_ascii=False)}], json_schema=schema)
            if not isinstance(response, dict) or response.get("status") != "ok":
                reason = "client_error"
            else:
                validate_report(response.get("result"), schema)
                report, mode = response["result"], "llm_reference_order"
        except (ValueError, TypeError, KeyError):
            reason = "invalid_structured_output"
        except Exception:
            reason = "client_unavailable"
    validate_report(report, schema)
    return {"status": "ok", "mode": mode, "fallback_reason": reason, "client_calls": calls,
            "report": report, "schema": schema, "evidence": deepcopy(bundle["evidence"]),
            "markdown": render_markdown(bundle, report, mode, reason)}
