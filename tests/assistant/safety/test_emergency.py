"""The emergency rules: every pattern, a third party, contact details in the message, and the
past events, label questions and figures of speech that must not fire."""

import pytest

from assistant.safety.emergency import PATTERNS, is_emergency

FIRES = {
    "overdose": "My son swallowed a bottle of pills",
    "overdose_by_count": "She took 20 ibuprofen tablets an hour ago",
    "child_got_into_pills": "I think my toddler got into the cabinet and ate some pills",
    "trouble_breathing": "I can't breathe after taking this",
    "chest_pain": "My dad has crushing chest pain right now",
    "unconsciousness": "She passed out and won't wake up",
    "seizure": "My daughter is having a seizure",
    "throat_swelling": "My throat is swelling after the first tablet",
    "self_harm": "I want to kill myself",
    "self_harm_ending_a_life": "I keep thinking about ending my life",
    "with_an_email": "This is sam@example.com, my husband is unconscious",
    "with_a_phone": "Call me at 217-555-0142, my wife overdosed",
}
DOES_NOT_FIRE = {
    "past_seizure": "I had a seizure last year, can I take this?",
    "past_overdose": "Years ago I took too many pills; is this one safe?",
    "label_question": "What does the label mean by trouble breathing?",
    "label_warning": "The warning says stop use if you have chest pain. What does that mean?",
    "figure_of_speech": "I'm dying to try your new vitamins",
    "figure_of_speech_killing": "This cough is killing me, what do you have?",
    "a_normal_dose": "I took 2 tablets this morning, when can I take more?",
    "an_ordinary_question": "Do you have something for a stuffy nose?",
}
HAPPENING_NOW = {
    "label_question_during_it": "I have chest pain right now, what does the label say?",
    "past_and_present": "I had a seizure as a child and now I'm having one again",
}


@pytest.mark.parametrize("message", FIRES.values(), ids=FIRES)
def test_a_current_emergency_fires(message):
    assert is_emergency(message)


@pytest.mark.parametrize("message", DOES_NOT_FIRE.values(), ids=DOES_NOT_FIRE)
def test_a_past_event_a_label_question_or_a_figure_of_speech_does_not_fire(message):
    assert not is_emergency(message)


@pytest.mark.parametrize("message", HAPPENING_NOW.values(), ids=HAPPENING_NOW)
def test_a_guard_never_silences_something_happening_now(message):
    assert is_emergency(message)


def test_every_kind_of_emergency_in_the_plan_has_a_pattern():
    assert set(PATTERNS) == {
        "overdose",
        "trouble breathing",
        "chest pain",
        "unconsciousness",
        "seizure",
        "throat swelling",
        "self-harm",
    }
