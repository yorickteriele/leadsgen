import pytest

from app.agents.kvk import KvkAgent, KvkLookupContext
from app.config import Settings
from app.models import WebsiteProfile


@pytest.mark.anyio
async def test_kvk_skips_without_api_key() -> None:
    agent = KvkAgent(Settings(KVK_API_KEY=None))

    profile, uncertainties = await agent.enrich(
        KvkLookupContext(domain="example.nl", website=WebsiteProfile())
    )

    assert profile.kvk_match_status == "not_found"
    assert profile.match_confidence == 0
    assert uncertainties == ["KvK API key not configured; KvK enrichment skipped"]
