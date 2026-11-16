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
        r"\b(?:too many|too much|handful"
        r"|(?:a whole|the whole|an entire|all of) (?:bottle|pack|packet|box)"
        r"|(?:bottle|pack|packet|box) of (?:pills?|tablets?|capsules?|caplets?|medicine|medication)"
        r"|\d{2,} (?:[a-z]+ ){0,3}(?:pills?|tablets?|capsules?|caplets?))\b"
        r"|\b(toddler|baby|child|kid|son|daughter|grandchild)\b[^.?!]{0,30}"
        r"\b(ate|swallowed|drank|got into|chewed)\b"
    ),
    "trouble breathing": (
        r"\b(can'?t|cannot|can not|unable to|struggling to|not|isn'?t|aren'?t|stopped)"
        r" breath(e|es|ing)?\b|\bcan'?t catch (my|his|her|their) breath\b"
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
    # Plurals only with "having": "does this cause seizures?" is a product question.
    "seizure": r"\b(seizure|seizing|convulsion|convulsing|having (seizures|convulsions))\b",
    "throat swelling": (
        r"\b(throat|tongue|lips?|face) (is |are |keeps )?(swelling|swollen|closing)\b"
        r"|\bswelling (of|in) (my|his|her|their|the) (throat|tongue|lips?|face)\b|\banaphyla"
        r"|\bthroat (feels? |is )?tight\b"
        r"|\btightness in (my|his|her|their|the) throat\b"
    ),
    "self-harm": (
        r"\b(kill(ing)? (myself|himself|herself|themselves)"
        r"|end(ing)? (my|his|her|their) (own )?life"
        r"|suicid\w*|hurt(ing)? (myself|himself|herself|themselves)|self[- ]harm"
        r"|wants? to die|don'?t want to (live|be alive)|take (my|his|her|their) (own )?life)\b"
    ),
}
# "When I was" dates something only with a life stage: "when I was out" can be minutes ago.
LIFE_STAGE = (
    r"when i was (?:pregnant|little|young|younger|small|a (?:kid|child|teen|teenager|baby)"
    r"|\d+)"
)
# Sentences that match a pattern above without reporting a current emergency.
GUARDS = {
    "past event": (
        r"\b(last|this past) (year|month|week|summer|winter|spring|fall|autumn)\b"
        r"|\b((\d+|a few|several|many) )?(years?|months?|weeks?) ago\b"
        rf"|\b{LIFE_STAGE}\b"
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
# An adjacent sentence may refer back to the symptom, but an unrelated 'now' cannot.
RECURRENCE = re.compile(
    r"^\s*(?:now[,]?\s+)?(?:i am|i'm|he is|he's|she is|she's|they are|they're|we are)"
    r"\s+having (?:one|it|that) (?:again|right now|now)\b"
    r"|^\s*(?:i am|i'm|he is|he's|she is|she's|they are|they're) having another one\b"
    r"|^\s*(?:i|we|they) have (?:it|that) again (?:right )?now\b",
    re.IGNORECASE,
)
SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
ELLIPSES = re.compile(r"\.{2,}|…")  # "my son... swallowed... the whole bottle" is one report
# A clause of its own starts with a subject or a question, not inside a label's symptom list.
SUBJECT = (
    r"(?:(?:now|today|tonight)\s+)?(?:i|he|she|they|we|my|his|her|their|our|am|are|is|what"
    r"|why|how|can|cannot|unable|does|do)\b"
)
CLAUSES = re.compile(
    rf"(?:[,;]\s*|\b(?:and|but|yet)\s+)(?=(?:{SUBJECT}|the\s+(?:label|warning)\b))",
    re.IGNORECASE,
)
# Openings that are nothing but a date or a label's lead-in belong to the clause after them:
# "Two years ago, I had a seizure", "The label says, do not use if ...".
DATES_IT = re.compile(
    r"(?:[\w-]+ ){0,2}(?:years?|months?|weeks?) ago|in the past|a while (?:ago|back)"
    r"|(?:last|this past) (?:year|month|week|summer|winter|spring|fall|autumn)"
    rf"|as a (?:kid|child|teen|teenager)|{LIFE_STAGE}",
    re.IGNORECASE,
)
QUOTES_LABEL = re.compile(
    r"(?:the|this|my) (?:label|warning|leaflet|instructions|insert) (?:says|said|reads|states)",
    re.IGNORECASE,
)
# A clause that says something is so now is never dated by the opening before it.
PRESENT = re.compile(
    r"\b(?:is|are|am|has|have|can'?t|cannot|won'?t|isn'?t|aren'?t|just|today|tonight)\b"
    r"|'(?:m|re)\b",
    re.IGNORECASE,
)
PERSON = re.compile(r"\s*(?:i|he|she|they|we|my|his|her|their|our)\b", re.IGNORECASE)
APOSTROPHES = str.maketrans({"’": "'", "‘": "'"})


def reports_emergency(sentence: str) -> bool:
    if not any(pattern.search(sentence) for pattern in EMERGENCY):
        return False
    if HAPPENING_NOW.search(sentence):
        return True
    return not any(guard.search(sentence) for guard in NOT_NOW)


def frames(opening: str, clause: str) -> bool:
    """Whether the opening only dates the clause after it, or introduces a label quote."""
    if QUOTES_LABEL.fullmatch(opening):
        return not PERSON.match(clause)  # a quote, not someone saying what happened
    lead = clause.split(",")[0]  # a later question (", so is this safe?") isn't the report
    return bool(DATES_IT.fullmatch(opening)) and not PRESENT.search(lead)


def clauses(sentence: str) -> list[str]:
    """Split at each new subject; a framing opening stays with the clause it frames."""
    parts = CLAUSES.split(sentence)
    if len(parts) > 1 and frames(parts[0].strip(), parts[1]):
        parts[:2] = [f"{parts[0]} {parts[1]}"]
    return parts


def is_emergency(message: str) -> bool:
    """Whether a sentence, or a clause of it beside a past event or label question, fires."""
    sentences = SENTENCES.split(ELLIPSES.sub(",", message.translate(APOSTROPHES)))
    return any(
        reports_emergency(sentence) or any(map(reports_emergency, clauses(sentence)))
        for sentence in sentences
    ) or any(
        RECURRENCE.search(current) and any(pattern.search(previous) for pattern in EMERGENCY)
        for previous, current in zip(sentences, sentences[1:], strict=False)
    )
