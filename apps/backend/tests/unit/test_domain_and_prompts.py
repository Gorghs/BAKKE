from __future__ import annotations

import subprocess
import sys

import pytest

from app.prompts import LLM_TASKS, PROMPT_VERSION, system_prompt, validate_task_output


def test_every_task_has_a_versioned_prompt():
    assert PROMPT_VERSION == "v1"
    for task in LLM_TASKS:
        text = system_prompt(task)
        assert "BAKKE" in text
        assert "Return ONLY valid JSON" in text


def test_typed_tasks_include_json_schema():
    text = system_prompt("generate_hypotheses")
    assert "Output JSON schema" in text
    assert "hypotheses" in text


def test_unknown_task_rejected():
    with pytest.raises(ValueError, match="unknown task"):
        system_prompt("decide_what_happened")


def test_valid_output_passes_contract():
    out = validate_task_output("critique", {"verdict": "PASS", "issues": []})
    assert out["verdict"] == "PASS"
    assert out["provider"] == ""  # defaults filled by the contract


def test_invalid_output_fails_loudly():
    with pytest.raises(ValueError, match="contract validation"):
        validate_task_output("critique", {"issues": []})  # missing verdict
    with pytest.raises(ValueError, match="expected a JSON object"):
        validate_task_output("critique", ["not", "a", "dict"])


def test_tasks_without_schema_pass_through():
    data = {"shared": ["a"], "differences": ["b"], "provider": "mock"}
    assert validate_task_output("compare_scenarios", data) is data


def test_domain_package_is_orm_and_adapter_free():
    """Domain imports must not pull in ORM models, adapters, API or SDKs."""
    code = """
import sys
import app.domain
import app.domain.scoring
import app.domain.dedup
import app.domain.ranking
import app.domain.constraints.engine
import app.domain.contracts
prefixes = ('app.models', 'app.adapters', 'app.api', 'app.infrastructure',
            'sqlalchemy', 'fastapi', 'httpx', 'openai')
bad = sorted(m for m in sys.modules if m.startswith(prefixes))
print('BAD:' + ','.join(bad))
raise SystemExit(1 if bad else 0)
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"domain pulled in forbidden modules: {proc.stdout}{proc.stderr}"
