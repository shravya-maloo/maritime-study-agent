"""The two things the AI does: write questions from notes, and grade answers.

Works with any OpenAI-compatible API. Set these in Maritime's env settings:

    LLM_API_KEY    your key (falls back to OPENAI_API_KEY, which Maritime
                   injects on plans that include AI credits)
    LLM_BASE_URL   leave empty for OpenAI; for a free Google Gemini key use
                   https://generativelanguage.googleapis.com/v1beta/openai/
    LLM_MODEL      e.g. gpt-4o-mini, or gemini-2.5-flash for Gemini
"""

import json
import os

from openai import OpenAI

QUESTIONS_PER_QUIZ = int(os.getenv("QUESTIONS_PER_QUIZ", "3"))


def _client():
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None
    if not api_key:
        raise RuntimeError("No LLM key set. Add LLM_API_KEY in Maritime's env settings.")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=20)


def _ask_for_json(prompt):
    response = _client().chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def make_questions(notes_text):
    """Turn a page of notes into a short list of {question, answer} pairs."""
    prompt = f"""You are a study coach. Write {QUESTIONS_PER_QUIZ} short-answer quiz
questions that test the most important ideas in these class notes. Mix recall
questions with one "explain why" question. Each answer should be 1-2 sentences.

Reply only with JSON like:
{{"questions": [{{"question": "...", "answer": "..."}}]}}

NOTES:
{notes_text[:12000]}"""
    return _ask_for_json(prompt)["questions"][:QUESTIONS_PER_QUIZ]


def grade(question, correct_answer, student_answer):
    """Return {"correct": true/false, "feedback": "one encouraging sentence"}."""
    prompt = f"""Grade a student's quiz answer. Be fair: accept answers that get
the main idea right even if the wording is different or incomplete.

Question: {question}
Correct answer: {correct_answer}
Student's answer: {student_answer}

Reply only with JSON like:
{{"correct": true, "feedback": "one short, friendly sentence"}}"""
    return _ask_for_json(prompt)
