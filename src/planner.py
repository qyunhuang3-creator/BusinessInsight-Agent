"""Planner 协议与确定性的演示实现；不连接任何 LLM。"""

from abc import ABC, abstractmethod
from src.context import AgentContext


class Planner(ABC):
    def create_plan(self, user_query: str) -> list[str]:
        return []

    @abstractmethod
    def next_action(self, context: AgentContext) -> dict:
        """根据问题、计划和已有 Observation 返回 action/arguments/reason。"""


class MockPlanner(Planner):
    """仅支持固定订单总数问题，用真实工具结果演示循环，不理解任意自然语言。"""

    DEMO_QUERY = "数据里一共有多少订单？"

    def create_plan(self, user_query):
        if user_query.strip().rstrip("？?") != self.DEMO_QUERY.rstrip("？"):
            return ["说明此 MockPlanner 不支持该问题"]
        return ["查询 orders 的总行数", "验证返回值并记录事实", "结束并回答订单总数"]

    def next_action(self, context):
        if context.user_query.strip().rstrip("？?") != self.DEMO_QUERY.rstrip("？"):
            return {"action": "finish", "arguments": {}, "reason": "MockPlanner 仅支持演示问题：数据里一共有多少订单？"}
        event = context.latest_observation()
        if event is None:
            return {"action": "run_sql", "arguments": {"query": "SELECT COUNT(*) AS order_count FROM orders"},
                    "reason": "需要查询订单总数"}
        observation = event["data"]
        rows = observation.get("rows", [])
        if (observation.get("status") == "ok" and observation.get("columns") == ["order_count"]
                and len(rows) == 1 and len(rows[0]) == 1
                and type(rows[0][0]) is int and rows[0][0] >= 0):
            context.add_finding(f"数据里一共有 {rows[0][0]:,} 个订单。", event["action_id"])
            reason = "已有足够证据回答用户问题"
        else:
            reason = "未获得有效的订单总数，无法确认答案"
        return {"action": "finish", "arguments": {}, "reason": reason}
