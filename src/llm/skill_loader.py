"""只加载方法 Skill；不允许任意路径或评测文件进入 Prompt。"""
from pathlib import Path
import re

SKILL_PATH = Path(__file__).resolve().parents[2] / "skills" / "root-cause-analysis" / "SKILL.md"


def analysis_skill(user_query):
    terms = r"归因|原因|驱动|异常|异动|下降|增长|root cause|why|declin|anomal"
    if not re.search(terms, user_query, re.I):
        return ""
    path = SKILL_PATH.resolve()
    expected_root = Path(__file__).resolve().parents[2] / "skills"
    if not path.is_relative_to(expected_root.resolve()):
        raise ValueError("Skill 路径必须位于项目 skills 内")
    return path.read_text(encoding="utf-8")
