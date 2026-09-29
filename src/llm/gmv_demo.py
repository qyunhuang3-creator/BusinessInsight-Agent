"""单次真实 GMV 分析记录器；没有预设 SQL 或异常月份。"""
import json
import os
from pathlib import Path
from src.agent import BusinessInsightAgent
from src.llm.llm_planner import LLMPlanner
from src.llm.openrouter_client import redact
from src.tools.sql_tool import run_sql
from src.tools.data_profiler import inspect_data


def main():
    os.environ.pop("OPENROUTER_API_KEY", None)
    trace = []
    sql_calls = 0

    class TracedPlanner(LLMPlanner):
        def next_action(self, context):
            entry = {"iteration": context.iteration, "planner_context": json.loads(self._context(context))}
            action = super().next_action(context)
            entry["llm_action"] = action
            trace.append(entry)
            print(redact(json.dumps(entry, ensure_ascii=False)), flush=True)
            return action

    def sql(query):
        nonlocal sql_calls
        sql_calls += 1
        observation = run_sql(query)
        trace[-1]["tool_observation"] = observation
        print(redact(json.dumps({"iteration": len(trace), "observation": observation}, ensure_ascii=False)), flush=True)
        return observation

    def profile():
        observation = inspect_data()
        trace[-1]["tool_observation"] = observation
        return observation

    planner = TracedPlanner()
    result = BusinessInsightAgent(planner, {"run_sql": sql, "inspect_data": profile}, max_iterations=10).run(
        "Olist 数据中是否存在 GMV 明显下降的完整月份？如果存在，主要由哪些因素驱动？")
    result.update(api_calls=planner.api_calls, sql_tool_calls=sql_calls, trace=trace)
    serialized = redact(json.dumps(result, ensure_ascii=False, indent=2))
    path = Path(__file__).resolve().parents[2] / "output" / "reports" / "gmv_agent_demo.json"
    path.write_text(serialized, encoding="utf-8")
    print(redact(json.dumps({k: v for k, v in result.items() if k not in ("trace", "context")}, ensure_ascii=False)), flush=True)
    return 0 if result["status"] == "finished" else 1


if __name__ == "__main__":
    raise SystemExit(main())
