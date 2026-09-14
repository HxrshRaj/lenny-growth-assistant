"""Deterministic intent router -- see app/services/router.py."""
from app.services.router import Intent, classify_intent


def test_plain_question_routes_to_qa():
    assert classify_intent("What makes a great PM?") == Intent.QA


def test_ship30_request_routes_to_essay_skill():
    assert classify_intent("Can you turn this into a Ship 30 for 30 essay?") == Intent.SHIP30_ESSAY
    assert classify_intent("write an essay about pricing based on that") == Intent.SHIP30_ESSAY


def test_html_artifact_request_routes_correctly():
    assert classify_intent("generate an HTML snippet showing this as a card") == Intent.ARTIFACT_HTML


def test_markdown_artifact_request_routes_correctly():
    assert classify_intent("create a markdown document summarizing this") == Intent.ARTIFACT_MARKDOWN


def test_follow_up_question_still_routes_to_qa():
    assert classify_intent("What about for an enterprise product instead?") == Intent.QA
