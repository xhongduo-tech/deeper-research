from types import SimpleNamespace

from app.api.reports import _select_download_markdown_content


def _msg(content: str):
    return SimpleNamespace(content=content)


def test_download_content_selection_skips_completion_notice():
    draft = (
        "# 2026年述职报告\n\n"
        "## 一、年度目标回顾\n\n"
        + "围绕业务目标推进重点项目，形成可复用的方法论。\n" * 30
        + "\n## 二、重点成果\n\n"
        + "沉淀关键指标、项目复盘和下一阶段计划。\n" * 30
    )
    notice = "报告已生成完毕！包含 7 个章节，约 9528 字。"

    selected = _select_download_markdown_content([_msg(notice), _msg(draft)])

    assert selected == draft.strip()
    assert "报告已生成完毕" not in selected


def test_download_content_selection_uses_latest_substantive_draft():
    older_draft = "# 旧版\n\n## 一、概览\n\n" + "旧内容\n" * 100
    revised_draft = "# 新版\n\n## 一、概览\n\n" + "新内容\n" * 100

    selected = _select_download_markdown_content([
        _msg("报告已生成完毕！包含 3 个章节，约 1800 字。"),
        _msg(revised_draft),
        _msg(older_draft),
    ])

    assert selected == revised_draft.strip()
