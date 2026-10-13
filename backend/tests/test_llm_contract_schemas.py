from __future__ import annotations

from app.providers.base import LLM_TASKS, TASK_RESPONSE_SCHEMAS
from app.providers.llm import OpenAILLMProvider


def _prompt(task: str) -> str:
    return OpenAILLMProvider(api_key="k", model="m", base_url="")._system_prompt(task)


class TestRealProviderPromptCarriesContract:
    """Real providers must receive the output contract in the prompt.

    Without it the model guesses the schema (observed live: gpt-oss-120b
    returned facts as plain strings, `type` instead of `entity_type` and
    `timeline` instead of `timeline_events`, so every extraction failed
    validation). The mock provider never needed the schema because its
    output is rule-based.
    """

    def test_every_registered_task_has_a_schema(self):
        assert set(LLM_TASKS) == set(TASK_RESPONSE_SCHEMAS)

    def test_extract_evidence_prompt_names_contract_keys(self):
        prompt = _prompt("extract_evidence")
        for key in ('"facts"', '"statement"', '"entities"', '"entity_type"', '"timeline_events"'):
            assert key in prompt, f"missing contract key {key}"

    def test_hypothesis_tasks_prompt_names_contract_keys(self):
        assert '"hypotheses"' in _prompt("generate_hypotheses")
        assert '"hypotheses"' in _prompt("expand_alternatives")
        assert '"verdict"' in _prompt("critique")
        assert '"revised"' in _prompt("revise")

    def test_dict_shaped_tasks_prompt_names_contract_keys(self):
        assert '"prompt"' in _prompt("expand_video_prompt")
        assert '"discriminating"' in _prompt("compare_scenarios")
        assert '"summary"' in _prompt("summarize_scenario")
        assert '"patterns"' in _prompt("similar_case_relevance")
