import pytest

from app.services.runtime_config import apply_runtime_config, is_external_search_enabled
from app.services.web_search_service import search_web


@pytest.mark.asyncio
async def test_external_search_is_forced_off_for_intranet_policy():
    apply_runtime_config({"enable_external_search": "true"})

    result = await search_web("latest AI slide generation")

    assert not is_external_search_enabled()
    assert result["enabled"] is False
    assert result["results"] == []
    assert "内网部署策略" in result["note"]
