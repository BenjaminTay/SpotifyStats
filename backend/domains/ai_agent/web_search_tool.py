"""Web search tool for AI Agent — uses Wikipedia as the primary backend."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.domains.ai_agent.tool_registry import AgentToolDefinition, AgentToolResult
from backend.providers.wikipedia.client import WikipediaProvider


class WebSearchParams(BaseModel):
    query: str = Field(..., min_length=1, max_length=300, description="Search query")
    language: str = Field(
        default="zh", description="Language code (zh for Chinese, en for English)"
    )
    limit: int = Field(default=3, ge=1, le=5, description="Max results")


def _web_search_handler(params: BaseModel) -> AgentToolResult:
    """Execute a web search via Wikipedia and return structured results."""
    parsed = WebSearchParams.model_validate(params)
    try:
        provider = WikipediaProvider()
        results = provider.search(
            parsed.query,
            language=parsed.language,
            limit=parsed.limit,
        )
    except Exception:
        return AgentToolResult(
            data={"results": [], "query": parsed.query},
            result_summary=f"web_search failed for '{parsed.query}'",
            source_range="web",
        )

    if not results:
        return AgentToolResult(
            data={"results": [], "query": parsed.query},
            result_summary=f"no Wikipedia results for '{parsed.query}'",
            source_range="web",
        )

    summaries = []
    for r in results:
        title = r.get("title", "")
        snippet = str(r.get("snippet", "") or r.get("extract", "") or "")
        url = r.get("url", "")
        summaries.append({"title": title, "snippet": snippet[:500], "url": url})

    return AgentToolResult(
        data={"results": summaries, "query": parsed.query},
        result_summary=f"web_search '{parsed.query}': {len(summaries)} results — {summaries[0]['title'] if summaries else 'none'}",
        source_range="web",
    )


WEB_SEARCH_TOOL = AgentToolDefinition(
    name="web_search",
    description="Search the web (Wikipedia) for artist background, album context, genre info, or music industry facts. Use for supplementary information not available in local playback data.",
    read_only=True,
    params_model=WebSearchParams,
    handler=_web_search_handler,
    cost="medium",
    supports_parallel=False,
    best_for=("本地数据没有的补充音乐背景", "艺人或专辑百科背景"),
    covers=("external_context",),
    cold_build_risk="none",
    avoid_when=("用户询问本地播放事实", "用户未请求外部背景"),
    fallback=(),
)
