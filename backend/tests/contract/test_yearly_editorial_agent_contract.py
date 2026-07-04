from backend.domains.ai_reports.editorial_agent import WRITER_PIPELINE_VERSION


def test_writer_pipeline_version_constant_is_cache_safe():
    assert WRITER_PIPELINE_VERSION == "yearly_editorial_agent_v1"
