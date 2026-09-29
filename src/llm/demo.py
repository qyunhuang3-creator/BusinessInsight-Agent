"""显式运行一次真实 Agent Demo；普通测试不调用此入口。"""
import json
import os
from src.agent import BusinessInsightAgent
from src.llm.llm_planner import LLMPlanner
from src.llm.openrouter_client import redact


def main():
    os.environ.pop("OPENROUTER_API_KEY", None)
    planner = LLMPlanner()
    result = BusinessInsightAgent(planner, max_iterations=10).run("数据里一共有多少订单？")
    result["api_calls"] = planner.api_calls
    print(redact(json.dumps(result, ensure_ascii=False, indent=2)))
    return 0 if result["status"] == "finished" else 1


if __name__ == "__main__":
    raise SystemExit(main())
