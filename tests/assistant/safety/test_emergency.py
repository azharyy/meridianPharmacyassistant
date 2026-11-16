"""The emergency rules: every pattern, a third party, contact details in the message, and the
past events, label questions and figures of speech that must not fire."""

import pytest

from assistant.safety.emergency import PATTERNS, is_emergency

FIRES = {
    "overdose": "My son swallowed a bottle of pills",
    "overdose_by_count": "She took 20 ibuprofen tablets an hour ago",
    "whole_medicine_bottle": "I swallowed a whole bottle of allergy medicine",
    "medicine_bottle": "I swallowed a bottle of pills",
    "handful": "I took a handful of tablets",
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
    "ordinary_strength": "I took 10 mg of cetirizine this morning",
    "whole_tablet": "I swallowed a whole tablet of aspirin",
    "water": "I drank a bottle of water",
    "an_ordinary_question": "Do you have something for a stuffy nose?",
}
HAPPENING_NOW = {
    "adjacent_recurrence": "I had a seizure last year. I am having one again now.",
    "adjacent_pain": "I had chest pain last year. I have it again now.",
    "adjacent_third_party": "My son had a seizure last year. He's having another one.",
    "tight_throat": "My throat feels tight right now",
    "throat_tightness": "There is tightness in my throat",
    "label_question_during_it": "I have chest pain right now, what does the label say?",
    "past_and_present": "I had a seizure as a child and now I'm having one again",
    "history_and_breathing": "I have a history of asthma and I cannot breathe",
    "shared_subject_cannot": "I have a history of asthma but cannot breathe",
    "shared_subject_unable": "I have a history of asthma, unable to breathe",
    "label_and_current_pain": "The warning says chest pain and I have chest pain",
    "curly_apostrophe": "I can’t breathe after taking this",
    "third_party_curly": "My dad won’t wake up",
    "present_then_label": "I have chest pain and what does the label say?",
    "comma_then_current": "The label mentions chest pain, I have chest pain",
    "past_then_it_now": "I had chest pain last year and I have it now",
    "past_then_one_now": "My son had a seizure last year, he is having one now",
    "past_then_another": "I had a seizure last week, and I'm having another one",
    "history_then_now": "I have a history of anaphylaxis and my throat feels tight right now",
    "label_then_that_now": "The warning mentions trouble breathing, I'm having that right now",
    # "Now" beside a symptom always fires: a false alarm costs less than a missed emergency.
    "past_then_well": "I had chest pain last year and am fine now",
    # An opening with more than a date or a label lead-in never silences the clause after it.
    "dated_opening_then_current": "A week ago I started Advil, my lips are swelling",
    "instructions_then_current": "The instructions said to take two, my son can't breathe",
    "leaflet_then_current": "The leaflet says it's safe, my throat is swelling",
    "like_the_warning": "Like the warning said, I have chest pain",
    "past_clause_then_current": "When I was little I had asthma; my son can't breathe",
    "since_then_current": "Since last week, I have chest pain",
    "bare_date_then_present": "Last week, I can't breathe properly",
    "today_then_current": "I had chest pain last year but today I have chest pain",
    "isnt_breathing": "My wife isn't breathing",
    "plural_seizures": "My son is having seizures",
    "plural_convulsions": "She is having convulsions",
    # "When I was <doing something>" can be minutes ago.
    "when_i_was_activity": "When I was in the shower, my toddler swallowed a bottle of pills",
    "when_i_was_asleep": "When I was asleep, my husband collapsed",
    "when_i_was_no_comma": "When I was out my dad collapsed. What do I do?",
    "label_lead_in_then_report": "The warning says, my son swallowed a bottle of pills",
    "dated_then_just": "Two weeks ago, my son started this medicine and just collapsed",
    "dated_then_today": "Last week, my dad started Advil and collapsed today",
    "catch_breath": "I can't catch my breath",
    "ellipsis": "my son... swallowed... the whole bottle",
}
DOES_NOT_FIRE.update(
    {
        "label_list": "The warning says chest pain and trouble breathing",
        "past_list": "I had a seizure last year and chest pain years ago",
        "opening_years_ago": "Two years ago, I had a seizure. Is this safe?",
        "opening_in_the_past": "In the past, I had trouble breathing after aspirin. Can I?",
        "opening_when_i_was": "When I was pregnant, I had chest pain. Is this ok?",
        "label_says_comma": "The label says, do not use if you have trouble breathing. Why?",
        "plural_side_effect_question": "Does this cause seizures?",
        "dated_then_question": "Years ago, I overdosed on Tylenol, so is this one safe?",
        "life_stage_age": "When I was 12 I had a seizure. Is this safe?",
        "breathable": "The mask isn't breathable",
        "dated_question_today": "Two years ago, I had a seizure, can I take this today?",
    }
)


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
