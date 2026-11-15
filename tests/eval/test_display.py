"""Displayed checks see widget text rather than hidden source bodies, IDs or model metadata."""

import json
from pathlib import Path

import pytest

from contracts.chat import ChatReply, HandoffReply
from eval.display import displayed, needs_judge

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"


@pytest.mark.parametrize("path", sorted((EXAMPLES / "replies").glob("*.json")))
def test_every_reply_example_has_displayed_text_and_only_catalog_evidence_needs_a_judge(path):
    reply = ChatReply.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert displayed(reply).strip()
    assert needs_judge(reply) == any(
        block.type in {"label_section", "comparison", "product_list", "policy_excerpt"}
        for block in reply.blocks
    )


def test_machine_metadata_and_hidden_source_text_cannot_satisfy_required_strings():
    reply = ChatReply.model_validate(
        {
            "reply_type": "off_topic",
            "blocks": [{"type": "text", "text": "Visible text."}],
            "sources": [
                {
                    "id": "api:orders",
                    "title": "Hidden metadata",
                    "text": "Unshown source.",
                    "retrieved_at": None,
                }
            ],
            "handoff_offered": False,
            "emergency": False,
        }
    )
    assert displayed(reply) == "Visible text."
    assert not needs_judge(reply)
    assert (
        displayed(HandoffReply(ticket_id=None, text="Confirmation text.")) == "Confirmation text."
    )
