"""Back up the router's prompt-injection label with a few pattern rules on the customer's message.

A match makes the turn's risk label prompt_injection: the pipeline logs the attempt, shows the
neutral refusal, and the conversation carries on. Least privilege does the real work (no
endpoint lists orders, the catalog agent can't reach them, the router never reads documents);
these rules are a backstop for the router's label.
"""

import re

PATTERNS = [
    r"\b(ignore|disregard|forget|override|bypass)\b[^.?!]{0,40}"
    r"\b(instructions|rules|prompt|guidelines|polic(y|ies)|restrictions)\b",
    r"\b(system|developer|hidden) (prompt|message|instructions)\b",
    r"\b(reveal|show|print|repeat|leak)\b[^.?!]{0,30}"
    r"\b(your )?(prompt|instructions|configuration)\b",
    r"\byou are now\b|\bpretend (to be|you are)\b",
    r"\b(jailbreak|developer mode)\b",
    r"\b(list|show|give|dump|export)\b[^.?!]{0,30}\b(all|every|other)\b[^.?!]{0,20}"
    r"\b(orders?|customers?|tickets?|emails?|addresses)\b",
]
INJECTION = [re.compile(pattern, re.IGNORECASE) for pattern in PATTERNS]


def looks_like_injection(message: str) -> bool:
    """Whether the redacted message tries to change the assistant's rules or reach other data."""
    return any(pattern.search(message) for pattern in INJECTION)
