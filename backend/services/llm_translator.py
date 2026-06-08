"""LLM translation service — translate Wikipedia text using user-configured LLM."""

import json
import logging
import re

from backend.providers.llm.client import LLMProvider

PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-haiku-4-5-20251001",
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "default_model": "",
    },
}

TRANSLATE_PROMPT = """你是一位专业翻译和文字排版师。将以下英文 Wikipedia 文本翻译成自然流畅的中文。

要求：
1. 翻译自然，如母语者所写
2. 保留原文的段落结构，段落之间用空行分隔
3. 艺人姓名、专辑名称、歌曲名用 **粗体** 标注
4. 引文、作品名（非专辑/歌曲）用 *斜体* 标注
5. 保持事实准确，不增删信息
6. 只输出翻译后的中文文本，不要加任何说明"""

ARTIST_ENRICH_PROMPT = """你是一位专业音乐百科编辑。请阅读以下英文 Wikipedia 完整文章，提取关键信息并输出 JSON。

要求：
1. 仔细阅读全文，提取所有重要事实
2. 只输出 JSON，用 ```json ``` 代码块包裹
3. 所有中文内容需自然流畅
4. JSON schema 如下：

{
  "summary": "1-2段中文概述，概括艺人核心信息",
  "key_facts": [
    {"label": "标签", "value": "内容"}
  ],
  "career_timeline": [
    {"year": 年份数字, "event": "事件标题", "detail": "简述"}
  ],
  "genres": ["风格1", "风格2"],
  "stats": [
    {"label": "指标名", "value": "数值"}
  ],
  "achievements": [
    {"title": "奖项/荣誉", "year": 年份数字, "detail": "补充说明"}
  ]
}

注意：
- key_facts: 提取5-8条基本事实（本名、出生、出道年份、厂牌、代表作等）
- career_timeline: 提取重要生涯节点，按年份升序，至少3条
- genres: 音乐风格列表
- stats: 提取4-6项关键数据（专辑数、奖项数、冠单数等），value 为字符串
- achievements: 提取重要奖项和荣誉
- 如某字段无内容则返回空数组 []"""

ALBUM_ENRICH_PROMPT = """你是一位专业音乐百科编辑。请阅读以下英文 Wikipedia 完整文章，提取关键信息并输出 JSON。

要求：
1. 仔细阅读全文，提取所有重要事实
2. 只输出 JSON，用 ```json ``` 代码块包裹
3. 所有中文内容需自然流畅
4. JSON schema 如下：

{
  "summary": "1-2段中文概述，概括专辑核心信息",
  "key_facts": [
    {"label": "标签", "value": "内容"}
  ],
  "genres": ["风格1", "风格2"],
  "chart_performance": [
    {"region": "榜单名", "peak": 最高排名数字, "detail": "补充信息"}
  ],
  "accolades": [
    {"title": "奖项/评价", "year": 年份数字, "detail": "补充说明"}
  ],
  "singles": [
    {"name": "单曲名", "peak": 最高排名数字, "certification": "认证"}
  ]
}

注意：
- key_facts: 提取5-8条基本事实（发行日期、厂牌、制作人、时长、曲风等）
- genres: 音乐风格列表
- chart_performance: 各国榜单表现，peak 为数字
- accolades: 重要奖项和好评
- singles: 主打单曲及榜单表现
- 如某字段无内容则返回空数组 []"""


logger = logging.getLogger(__name__)


def _get_config():
    """Read LLM settings from the backend settings module."""
    try:
        import backend.api.settings as settings_mod

        if settings_mod._current is None:
            settings_mod._ensure_current()
        return settings_mod._current or {}
    except Exception:
        return {}


def translate_with_llm(text):
    """Translate text using the configured LLM. Returns translated string or ''."""
    if not text or not text.strip():
        return ""

    cfg = _get_config()
    if not cfg.get("llm_enabled") or not cfg.get("llm_api_key"):
        return ""

    provider = cfg.get("llm_provider", "deepseek")
    api_key = cfg["llm_api_key"]
    model = cfg.get("llm_model") or PROVIDERS.get(provider, {}).get("default_model", "")
    base_url = cfg.get("llm_base_url") or PROVIDERS.get(provider, {}).get("base_url", "")

    if provider == "anthropic":
        return _translate_anthropic(text, api_key, model, base_url)
    else:
        if not base_url:
            return ""
        return _translate_openai_compat(text, api_key, model, base_url, provider=provider)


def enrich_with_llm(full_text, entity_type):
    """Send full Wikipedia article to LLM, get structured JSON back. Returns dict or None."""
    if not full_text or not full_text.strip():
        return None

    cfg = _get_config()
    if not cfg.get("llm_enabled") or not cfg.get("llm_api_key"):
        return None

    provider = cfg.get("llm_provider", "deepseek")
    api_key = cfg["llm_api_key"]
    model = cfg.get("llm_model") or PROVIDERS.get(provider, {}).get("default_model", "")
    base_url = cfg.get("llm_base_url") or PROVIDERS.get(provider, {}).get("base_url", "")

    if entity_type == "album":
        prompt = ALBUM_ENRICH_PROMPT
    else:
        prompt = ARTIST_ENRICH_PROMPT

    # Truncate to avoid excessive tokens (30k chars ≈ 7.5k tokens)
    text = full_text.strip()[:30000]

    try:
        if provider == "anthropic":
            raw = _translate_anthropic(text, api_key, model, base_url, prompt=prompt)
        else:
            if not base_url:
                return None
            raw = _translate_openai_compat(
                text,
                api_key,
                model,
                base_url,
                prompt=prompt,
                provider=provider,
            )
    except Exception:
        return None

    if not raw:
        return None

    return _parse_enrich_json(raw)


def _parse_enrich_json(raw):
    """Extract and parse JSON from LLM output. Returns dict or None."""
    # Try to extract ```json ... ``` block first
    import re as _re

    m = _re.search(r"```(?:json)?\s*\n?(.+?)\n?```", raw, _re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    # Try parsing the raw response directly
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    # Try to find a JSON object in the response
    m = _re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _translate_openai_compat(text, api_key, model, base_url, prompt=None, provider="openai"):
    """Translate via OpenAI-compatible chat/completions API."""
    llm = LLMProvider(provider=provider, api_key=api_key, model=model, base_url=base_url)

    if len(text) <= 4000:
        chunks = [text]
    else:
        chunks = _chunk_text(text, 4000)

    results = []
    for chunk in chunks:
        try:
            data = llm.chat(
                [
                    {"role": "system", "content": prompt if prompt else TRANSLATE_PROMPT},
                    {"role": "user", "content": chunk},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            content = (data or {}).get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                results.append(content)
        except Exception:
            results.append("")
            logger.warning("LLM translation chunk failed", exc_info=True)

    return "\n\n".join(results)


def _translate_anthropic(text, api_key, model, base_url, prompt=None):
    """Translate via Anthropic Messages API."""
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    llm = LLMProvider(provider="anthropic", api_key=api_key, model=model, base_url=base_url)

    if len(text) <= 4000:
        chunks = [text]
    else:
        chunks = _chunk_text(text, 4000)

    results = []
    for chunk in chunks:
        try:
            data = llm.chat(
                [
                    {"role": "system", "content": prompt if prompt else TRANSLATE_PROMPT},
                    {"role": "user", "content": chunk},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            content = (data or {}).get("content", [{}])[0].get("text", "")
            if content:
                results.append(content)
        except Exception:
            results.append("")
            logger.warning("LLM translation chunk failed", exc_info=True)

    return "\n\n".join(results)


def _chunk_text(text, max_len):
    """Split text at paragraph boundaries, respecting max_len."""
    paragraphs = re.split(r"\n\n+", text)
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < max_len:
            current += ("\n\n" + para) if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks
