"""One-command demo: offline validated replay by default; explicit live opt-in."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.demo_business_report import example_bundle
from src.report_generator import generate_report, sources_from_context

DEFAULT_QUESTION = "Why did Product GMV decline, and what were the main drivers?"
SUPPORTED = {DEFAULT_QUESTION, "Why did Product GMV decline?",
             "Olist 数据中是否存在 GMV 明显下降的完整月份？如果存在，主要由哪些因素驱动？"}
STAGES = ["Business Question", "Data Inspection", "Metric Analysis", "Anomaly Detection",
          "Root Cause Analysis", "Evidence Validation", "Final Report"]


def supported(question):
    normalize = lambda s: re.sub(r"\s+", " ", s.strip()).rstrip("?？").casefold()
    return normalize(question) in {normalize(q) for q in SUPPORTED}


def safe(value):
    """No environments, remote exception text or reasoning are serialized."""
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, str):
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            value = value.replace(key, "[REDACTED]")
        value = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        if re.search(r"authorization|api[_ -]?key|password|secret|bearer", value, re.I):
            return "[Sensitive text omitted]"
    return value


def live_run(question):
    # Lazy imports: offline replay needs only Python stdlib and no key.
    from src.agent import BusinessInsightAgent
    from src.llm.llm_planner import LLMPlanner
    planner = LLMPlanner()
    run = BusinessInsightAgent(planner, max_iterations=10).run(question)
    return run, planner.api_calls


def observed_bundle(run, question):
    """Literal SQL observations only, not automatic business-semantic mapping."""
    sources = sources_from_context(run.get("context", {"history": []}))
    evidence = []
    for sid, source in sources.items():
        obs = source["data"]
        if source["tool"] != "run_sql":
            continue
        for index, row in enumerate(obs.get("rows", [])):
            values, refs = {}, {}
            for col, value in enumerate(row):
                if value is None or type(value) in (str, bool, int, float):
                    name = f"{col}: {obs['columns'][col]}"
                    values[name], refs[name] = value, ["rows", index, col]
            if values:
                evidence.append({"id": f"{sid}_row_{index}", "section": "anomaly_overview",
                    "metric": "Observed SQL result", "period": "See source query",
                    "dimension": "See source columns; semantic mapping not validated",
                    "source_id": sid, "values": values, "references": refs})
    return {"question": question, "analysis_status": "Agent finish; report semantic mapping incomplete",
        "origin": "Live Agent observations only", "sources": sources, "evidence": evidence,
        "hypotheses": {}, "limitations": {"mapping": "Only literal successful SQL results are mapped. Automated decomposition/attribution mapping and final answer semantics remain unverified; truncated results are not complete rankings."},
        "recommended_next_checks": {"review": "Review query grain, periods, units and evidence mappings before accepting the business conclusion."}}


def headline(bundle):
    e = {r["id"]: r["values"] for r in bundle["evidence"]}
    g = e["gmv"]
    driver = e["driver"]["main_driver"]
    contribution = e["volume"]["volume_contribution_pct"] if driver == "Order Volume" else e["aov_effect"]["aov_contribution_pct"]
    lines = [f"Selected Period: {g['previous_month']} → {g['current_month']}",
        f"Product GMV: {g['previous_gmv']:,.2f} → {g['current_gmv']:,.2f}",
        f"MoM: {g['gmv_mom_pct']:.2f}%", f"Primary Metric Driver: {driver}", f"Contribution: {contribution:.2f}%"]
    for label, eid in [("Category", "top_product_category"), ("State", "top_customer_state"), ("Seller", "top_seller")]:
        lines.extend([f"Largest {label} Contributor: {e[eid]['member']}",
                      f"Contribution: {e[eid]['contribution_to_total_decline_pct']:.2f}%"])
    return "\n".join(lines)


def run_demo(mode="offline", question=DEFAULT_QUESTION, output_dir=None, agent_runner=None):
    output = Path(output_dir) if output_dir else ROOT / "output/demo"
    output = output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Demo output must stay inside project")
    output.mkdir(parents=True, exist_ok=True)
    # Delivery-only path selection: keep the author's workbook, use the public
    # relative-path copy in a clean checkout. No analysis behavior changes.
    tableau_path = "output/tableau/BusinessInsight_Dashboard.twb"
    if not (ROOT / tableau_path).is_file():
        tableau_path = "output/tableau/BusinessInsight_Dashboard_public.twb"
    trace = {"mode": mode, "question": question, "stages": [], "evidence_references": [],
             "fallback_used": False, "report_path": None, "tableau_path": tableau_path,
             "completion_status": "started", "api_calls": 0}
    summary = "No completed analysis."
    def stage(index, origin, detail):
        trace["stages"].append({"stage": STAGES[index-1], "origin": origin, "detail": detail})
        print(f"[{index}/7] {STAGES[index-1]} — {origin}: {safe(detail)}")
    try:
        if mode not in ("offline", "agent"):
            raise ValueError("Invalid mode")
        stage(1, mode, question)
        if mode == "offline" and not supported(question):
            print("当前 Offline Demo 是保存分析流程的 deterministic replay，而不是实时通用 Agent。Unsupported question.")
            trace["completion_status"] = "unsupported_question"
            return 2
        replay = mode == "offline"
        if not replay:
            print("Live Agent: openrouter/free, max_iterations=10. No automatic API retry.")
            try:
                run, calls = (agent_runner or live_run)(question)
                trace["api_calls"] = calls
                trace["agent_status"] = run.get("status")
                trace["agent_iterations"] = run.get("context", {}).get("iteration", 0)
                trace["agent_events"] = []
                for event in run.get("context", {}).get("history", []):
                    data = event.get("data", {})
                    trace["agent_events"].append({"type": event.get("type"), "action_id": event.get("action_id"),
                        "action": data.get("action"), "status": data.get("status"),
                        "row_count": data.get("row_count"), "error_code": data.get("error", {}).get("code"),
                        "http_status": data.get("diagnostics", {}).get("http_status")})
                replay = run.get("status") != "finished"
            except Exception:
                trace["agent_status"] = "runner_error"
                trace["api_calls"] = None  # Unknown, not falsely zero.
                replay = True
            if replay:
                trace["fallback_reason"] = trace["agent_status"]
                if not supported(question):
                    trace["completion_status"] = "agent_failed_no_matching_replay"
                    print("Agent unavailable; no matching validated replay for this question.")
                    return 2
                trace["fallback_used"] = True
                print("Agent did not complete. Falling back to deterministic validated analysis. NOT an Agent-generated conclusion.")
        if replay:
            bundle = example_bundle()  # Only after the live loop has stopped.
            bundle["question"] = question
            stage(2, "saved evidence replay", "Existing data quality/coverage checks; no fresh profiling.")
            stage(3, "saved evidence replay", "Product GMV / valid-item Order Volume / AOV; no new calculation.")
            stage(4, "saved evidence replay", "Existing comparable-period anomaly selection.")
            stage(5, "saved evidence replay", "Existing symmetric decomposition, category/state/seller attribution and drill-down.")
        else:
            bundle = observed_bundle(run, question)
            for i in range(2, 6):
                stage(i, "live observations", "See actual tool results; stage semantics not independently certified.")
        result = generate_report(bundle)
        if result["status"] != "ok":
            raise ValueError("Invalid evidence")
        stage(6, "deterministic validation", f"Validated {len(result['evidence'])} evidence records against source fields.")
        if replay:
            report_path = (ROOT / "output/reports/agent_business_report.md") if output_dir is None else output / "replay_business_report.md"
        else:
            report_path = output / "live_agent_report.md"
        report_path.write_text(safe(result["markdown"]), encoding="utf-8")
        trace["report_path"] = report_path.relative_to(ROOT).as_posix()
        trace["evidence_references"] = [{"id": e["id"], "source": bundle["sources"][e["source_id"]]["reference"], "fields": e["references"]} for e in bundle["evidence"]]
        trace["completion_status"] = "completed_replay" if replay else "agent_finished_report_partial"
        stage(7, result["mode"], trace["report_path"])
        summary = headline(bundle) if replay else "Agent finished. Literal observations saved; business-semantic report mapping remains incomplete. No Ground Truth used."
        print(summary)
        print("Final Report:", trace["report_path"])
        print("Tableau Dashboard:", trace["tableau_path"])
        trace["tableau_available"] = (ROOT / trace["tableau_path"]).is_file()
        if not trace["tableau_available"]:
            print("Dashboard file missing locally; obtain the supplied visualization deliverable.")
        trace["result"] = summary
        return 0
    except Exception:
        trace["completion_status"] = "failed"
        print("Demo could not complete. Check local validated evidence and output permissions. No API retry; no raw exception logged.")
        return 1
    finally:
        (output / "demo_trace.json").write_text(json.dumps(safe(trace), ensure_ascii=False, indent=2), encoding="utf-8")
        text = (f"# BusinessInsight Demo\n\nMode: {mode}\n\nQuestion: {question}\n\n"
                f"Status: {trace['completion_status']}\n\nFallback: {trace['fallback_used']}\n\n"
                "Business Question → Data Inspection → Metric Analysis → Anomaly Detection → Root Cause Analysis → Evidence Validation → Business Report → Tableau Dashboard\n\n"
                "Offline/fallback is saved deterministic evidence replay, not live LLM reasoning. Tableau was built and verified by the user.\n\n"
                f"```text\n{summary}\n```\n\nReport: {trace['report_path']}\n\nDashboard: {trace['tableau_path']}\n")
        (output / "demo_summary.md").write_text(safe(text), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="BusinessInsight: offline validated replay (default), optional live Agent")
    parser.add_argument("--mode", choices=("offline", "agent"), default="offline")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args(argv)
    try:
        return run_demo(args.mode, args.question)
    except Exception:
        print("Demo could not write its output. Check project paths and permissions.")
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
