"""Test Ollama failure fallback."""
from app.ai.local_llm import LocalLLMProvider
from unittest.mock import patch
from app.config.settings import settings

provider = LocalLLMProvider()
print("--- TEST: Ollama failure -> Fast NLP fallback ---")
with patch.object(settings, "LOCAL_AI_URL", "http://localhost:99999/api/generate"):
    res = provider.analyze_document(
        title="Trading Suspension of XYZ Ltd for non-compliance",
        category="Surveillance",
        content="Trading in securities of XYZ Ltd shall be suspended w.e.f. 15-10-2026."
    )
print(f"Priority: {res['priority']}")
print(f"Event type: {res['event_type']}")
print(f"Effective date: {res['effective_date']}")
print(f"Analysis mode: {res['analysis_mode']}")
print(f"Summary: {res['summary'][:120]}")
assert res["priority"] == "CRITICAL"
assert res["analysis_mode"] == "FAST_NLP"
assert "15-10-2026" in res["effective_date"]
print("PASS: Ollama fallback to Fast NLP works correctly")
