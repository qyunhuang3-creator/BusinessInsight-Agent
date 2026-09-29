"""可替换 Planner 的执行循环；当前演示使用 MockPlanner，不连接 LLM。"""

import inspect
import json
from src.context import AgentContext
from src.planner import Planner, MockPlanner
from src.tools.data_profiler import inspect_data
from src.tools.sql_tool import run_sql


def error_observation(code, message):
    return {"status": "error", "error": {"code": code, "message": message}}


class BusinessInsightAgent:
    def __init__(self, planner: Planner, tool_registry=None, max_iterations=10):
        if type(max_iterations) is not int or max_iterations < 1:
            raise ValueError("max_iterations 必须是正整数")
        self.planner = planner
        self.max_iterations = max_iterations
        self.tool_registry = dict(tool_registry) if tool_registry is not None else {
            "inspect_data": inspect_data, "run_sql": run_sql,
        }

    def _execute(self, action):
        tool = self.tool_registry.get(action["action"])
        if not callable(tool):
            return error_observation("unknown_tool", f"Tool 不存在：{action['action']}")
        try:
            inspect.signature(tool).bind(**action["arguments"])
        except (TypeError, ValueError) as exc:
            return error_observation("invalid_arguments", str(exc))
        try:
            result = tool(**action["arguments"])
        except Exception as exc:
            return error_observation("tool_exception", f"{type(exc).__name__}: {exc}")
        if not isinstance(result, dict) or result.get("status") not in ("ok", "partial", "error"):
            return error_observation("invalid_observation", "Tool 必须返回包含 status 的 dict")
        return result

    @staticmethod
    def _valid_action(action):
        return (isinstance(action, dict) and set(action) == {"action", "arguments", "reason"}
                and isinstance(action["action"], str) and bool(action["action"].strip())
                and isinstance(action["arguments"], dict)
                and all(isinstance(k, str) for k in action["arguments"])
                and isinstance(action["reason"], str)
                and (action["action"] != "finish" or not action["arguments"]
                     or (set(action["arguments"]) == {"answer"}
                         and isinstance(action["arguments"]["answer"], str)
                         and bool(action["arguments"]["answer"].strip()))))

    def run(self, user_query):
        if not isinstance(user_query, str) or not user_query.strip():
            raise ValueError("user_query 必须是非空字符串")
        context = AgentContext(user_query=user_query)

        def result(status, reason):
            return {"status": status, "answer": "\n".join(f["statement"] for f in context.findings) or reason,
                    "stop_reason": reason, "context": context.to_dict()}

        try:
            plan = self.planner.create_plan(user_query)
            if not isinstance(plan, list) or not all(isinstance(s, str) for s in plan):
                raise ValueError("计划必须是字符串列表")
            context.set_plan(plan)
        except Exception as exc:
            context.add_observation(error_observation("planner_error", str(exc)))
            return result("error", "Planner 生成计划失败")
        for iteration in range(1, self.max_iterations + 1):
            context.iteration = iteration
            try:
                action = self.planner.next_action(context)
            except Exception as exc:
                context.add_observation(error_observation("planner_error", str(exc)))
                return result("error", "Planner 决策失败")
            if isinstance(action, dict) and action.get("status") == "error":
                context.add_observation(action)
                return result("error", "Planner 返回错误，未执行动作")
            if not self._valid_action(action):
                context.add_observation(error_observation("invalid_action", "Planner Action 格式非法"))
                return result("error", "Planner 返回非法 Action")
            action_id = context.add_action(action)
            if action["action"] == "finish":
                latest = context.latest_observation()
                status = "error" if latest and latest["data"].get("status") == "error" else "finished"
                final = result(status, action["reason"])
                if "answer" in action["arguments"]:
                    final["answer"] = action["arguments"]["answer"]
                return final
            observation = self._execute(action)
            context.add_observation(observation, action_id)
            # 错误也作为 Observation 交回 Planner，允许下一轮调整；循环上限仍生效。
        context.add_observation(error_observation("max_iterations", "达到最大循环次数，安全停止"))
        return result("max_iterations", "达到最大循环次数，安全停止")


def main():
    print("MockPlanner Demo：确定性规则规划器，不是 LLM Agent")
    result = BusinessInsightAgent(MockPlanner()).run(MockPlanner.DEMO_QUERY)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "finished" and result["context"]["findings"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
