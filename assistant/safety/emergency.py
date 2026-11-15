"""Step 1: recognise a report of a current emergency in the raw message, before anything else.

It runs before redaction and before any model call, in any conversation state, and it fires
whether the person in danger is the customer or someone else. It only says whether a message
reports an emergency; the 911 reply is built by the renderer. A past event, a question about
what a label warning means, or a figure of speech ("I'm dying to try your new vitamins")
doesn't fire. A sentence that also says something is happening now always fires.
"""

import re

# Each kind of current emergency, as the patterns that report it.
PATTERNS = {
    "overdose": (
        r"\boverdos|\bpoison(ed|ing)\b"
        r"|\b(took|taken|swallowed|swallowing|ate|drank)\b[^.?!]{0,40}?"
        r"\b(too many|too much|a whole|the whole|an entire|all of|\d{2,}|bottle|pack|packet|box"
        r"|handful)\b"
        r"|\b(toddler|baby|child|kid|son|daughter|grandchild)\b[^.?!]{0,30}"
        r"\b(ate|swallowed|drank|got into|chewed)\b"
    ),
    "trouble breathing": (
        r"\b(can'?t|cannot|can not|unable to|struggling to|not|stopped) breath"
        r"|\b(trouble|difficulty|hard time) breathing\b|\bshort(ness)? of breath\b"
    ),
    "chest pain": (
        r"\bchest (pain|pains|pressure|tightness|hurts)\b"
        r"|\b(pain|pressure|tightness) in (my|his|her|their|the) chest\b"
    ),
    "unconsciousness": (
        r"\b(unconscious|unresponsive|passed out|blacked out|fainted|collapsed"
        r"|won'?t wake up|not waking up|can'?t wake (him|her|them) up)\b"
    ),
    "seizure": r"\b(seizure|seizing|convulsion|convulsing)\b",
    "throat swelling": (
        r"\b(throat|tongue|lips?|face) (is |are |keeps )?(swelling|swollen|closing)\b"
        r"|\bswelling (of|in) (my|his|her|their|the) (throat|tongue|lips?|face)\b|\banaphyla"
    ),
    "self-harm": (
        r"\b(kill(ing)? (myself|himself|herself|themselves)"
        r"|end(ing)? (my|his|her|their) (own )?life"
        r"|suicid\w*|hurt(ing)? (myself|himself|herself|themselves)|self[- ]harm"
        r"|wants? to die|don'?t want to (live|be alive)|take (my|his|her|their) (own )?life)\b"
    ),
}
# Sentences that match a pattern above without reporting a current emergency.
GUARDS = {
    "past event": (
        r"\b(last|this past) (year|month|week|summer|winter|spring|fall|autumn)\b"
        r"|\b((\d+|a few|several|many) )?(years?|months?|weeks?) ago\b|\bwhen I was\b"
        r"|\bas a (kid|child|teen|teenager)\b|\bin the past\b|\bhistory of\b|\bused to\b"
        r"|\ba while (ago|back)\b"
    ),
    "label question": (
        r"\b(label|warning|warnings|leaflet|instructions|insert)\b[^.?!]*"
        r"\b(say|says|said|mean|means|meant|mention|mentions)\b"
        r"|\bwhat (does|do|is) [^.?!]*\b(label|warning)"
    ),
}
# Words that say it is happening now; they override every guard.
NOW = (
    r"\b(now|right now|currently|at the moment|is having|are having|am having|i'?m having"
    r"|he'?s having|she'?s having|they'?re having|isn'?t breathing|won'?t wake)\b"
)

EMERGENCY = [re.compile(pattern, re.IGNORECASE) for pattern in PATTERNS.values()]
NOT_NOW = [re.compile(pattern, re.IGNORECASE) for pattern in GUARDS.values()]
HAPPENING_NOW = re.compile(NOW, re.IGNORECASE)
SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")


def reports_emergency(sentence: str) -> bool:
    if not any(pattern.search(sentence) for pattern in EMERGENCY):
        return False
    if HAPPENING_NOW.search(sentence):
        return True
    return not any(guard.search(sentence) for guard in NOT_NOW)


def is_emergency(message: str) -> bool:
    """Whether any sentence of the raw message reports a current emergency."""
    return any(reports_emergency(sentence) for sentence in SENTENCES.split(message))
