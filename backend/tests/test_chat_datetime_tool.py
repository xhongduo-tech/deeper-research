from datetime import datetime
from zoneinfo import ZoneInfo

from app.api.chat import _answer_with_current_datetime_tool


def test_current_datetime_tool_answers_month_day():
    now = datetime(2026, 6, 4, 11, 48, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert _answer_with_current_datetime_tool("今天是几月几日", now) == "今天是6月4日。"


def test_current_datetime_tool_answers_weekday_with_full_date():
    now = datetime(2026, 6, 4, 11, 48, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert _answer_with_current_datetime_tool("今天周几？", now) == "今天是2026年6月4日，星期四。"


def test_current_datetime_tool_leaves_live_external_queries_to_normal_flow():
    now = datetime(2026, 6, 4, 11, 48, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert _answer_with_current_datetime_tool("今天北京天气怎么样？", now) is None
