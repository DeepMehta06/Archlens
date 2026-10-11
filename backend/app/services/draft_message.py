"""Client clarification message drafting (English or Hinglish). Output is an editable draft."""
from typing import Any

from app.models import Question
from app.services.prompts import load_prompt


async def draft_message(llm: Any, questions: list[Question], language: str) -> str:
    if not questions:
        raise ValueError("There are no open questions to draft a message about.")
    numbered = "\n".join(f"{i}. {q.question}" for i, q in enumerate(questions, start=1))
    messages = [
        {"role": "system", "content": load_prompt("draft_message")},
        {"role": "user", "content": f"Language: {language}\nQuestions:\n{numbered}"},
    ]
    result = await llm.chat(messages, temperature=0.4, think=False, stage="draft_message")
    text = result.content.strip()
    if not text:
        raise ValueError("The model returned an empty draft; try again.")
    return text
