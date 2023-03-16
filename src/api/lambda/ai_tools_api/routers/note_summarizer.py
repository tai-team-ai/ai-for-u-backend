import logging
import os
from pathlib import Path
import sys
import threading
from typing import Optional
from fastapi import APIRouter, Response, status, Request
import openai
from pydantic import constr

sys.path.append(Path(__file__, "../").absolute())
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response, GeneratorWrapper
from utils import CamelCaseModel, UUID_HEADER_NAME, update_user_token_count, sanitize_string

router = APIRouter()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


KEYWORDS_FOR_PROMPT ={
    "summary_sentence": "1-3 sentence summary",
    "bullets": "bullet points",
    "action_items": "action items",
    "freeform_command": "freeform text analysis command"
}

SECTIONS_FOR_RESPONSE = {
    "summary_sentence": "Summary Sentence:\n",
    "bullets": "Bullet Points:\n",
    "action_items": "Action Items:\n",
    "freeform_command": "Freeform Text Analysis:\n"
}

MAX_TOKENS = 400

SYSTEM_PROMPT = (
    "You are a professional text summarizer. You job is to summarize & analyze the text for me in order to help me "
    f"understand the text better. I may optional ask you to provide me with a {KEYWORDS_FOR_PROMPT['summary_sentence']}, "
    f"{KEYWORDS_FOR_PROMPT['bullets']}, {KEYWORDS_FOR_PROMPT['action_items']}, and a {KEYWORDS_FOR_PROMPT['freeform_command']}. "
    f"You should only include these sections if I ask for them. If I provide a {KEYWORDS_FOR_PROMPT['freeform_command']}, "
    "you should analyze the text using the command I provide. However, if the command is not related to text analysis, "
    "you should ignore it. You should also ignore any commands that are not related to text analysis. For each of the "
    f"sections I provide you should title the section as follows: {SECTIONS_FOR_RESPONSE['summary_sentence']}, "
    f"{SECTIONS_FOR_RESPONSE['bullets']}, {SECTIONS_FOR_RESPONSE['action_items']}, and {SECTIONS_FOR_RESPONSE['freeform_command']}. "
)

ENDPOINT_NAME = "text-summarizer"


class TextSummarizerRequestModel(CamelCaseModel):
    text_to_summarize: str
    include_summary_sentence: Optional[bool]
    number_of_bullets: Optional[int]
    number_of_action_items: Optional[int]
    freeform_command: Optional[constr(min_length=1, max_length=200)]

class TextSummarizerResponseModel(CamelCaseModel):
    summary_sentence: Optional[str]
    bullet_points: Optional[str]
    action_items: Optional[str]
    freeform_section: Optional[str]
    

class TextSummarizerExampleResponse(CamelCaseModel):
    example_names: list[str]
    examples: list[TextSummarizerRequestModel]
    
    
@router.get(f"/{ENDPOINT_NAME}-examples", response_model=TextSummarizerExampleResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> TextSummarizerExampleResponse:
    """Return examples for the text summarizer endpoint."""
    examples = [
        TextSummarizerRequestModel(
            text_to_summarize="This is a test. This is only a test. This is a test of the emergency broadcast system. ",
            include_summary_sentence=True,
            number_of_bullets=3,
            number_of_action_items=2,
            freeform_command="Count the number of characters and group them by character."
        )
    ]
    response = TextSummarizerExampleResponse(
        example_names=["Example 1"],
        examples=examples
    )
    return response

@router.post(f"/{ENDPOINT_NAME}", response_model=TextSummarizerResponseModel, status_code=status.HTTP_200_OK)
async def text_summarizer(text_summarizer_request: TextSummarizerRequestModel, request: Request):
    logger.info(f"Text Summarizer Request Model: {text_summarizer_request}")
    for field_name, value in text_summarizer_request:
        if isinstance(value, str):
            setattr(text_summarizer_request, field_name, value.strip())
    system_prompt = SYSTEM_PROMPT
    if text_summarizer_request.include_summary_sentence:
        system_prompt += f"Please provide me with a {KEYWORDS_FOR_PROMPT['summary_sentence']}. "
    if text_summarizer_request.number_of_bullets:
        system_prompt += f"Please provide me with {text_summarizer_request.number_of_bullets} {KEYWORDS_FOR_PROMPT['bullets']}. "
    if text_summarizer_request.number_of_action_items:
        system_prompt += f"Please provide me with {text_summarizer_request.number_of_action_items} {KEYWORDS_FOR_PROMPT['action_items']}. "
    if text_summarizer_request.freeform_command:
        system_prompt += f"Here's my {KEYWORDS_FOR_PROMPT['freeform_command']}: {text_summarizer_request.freeform_command}. "

    system_prompt += "Finally, here's the text I want you to summarize: "

    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=text_summarizer_request.text_to_summarize
    )
    chat_session = GPTTurboChatSession(messages=[user_chat])
    generator = GeneratorWrapper(
        get_gpt_turbo_response(
            system_prompt=system_prompt,
            chat_session=chat_session,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            temperature=0.3,
            uuid=uuid,
            max_tokens=MAX_TOKENS
        )
    )
    try:
        next(generator)
    except StopIteration:
        chat_session = generator.value
    latest_gpt_chat_model = chat_session.messages[-1]
    update_user_token_count(uuid, latest_gpt_chat_model.token_count)
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)

    try:
        summary_sentence = latest_chat.split(SECTIONS_FOR_RESPONSE["summary_sentence"])[-1].split(SECTIONS_FOR_RESPONSE["bullets"])[0].strip()
    except:
        summary_sentence = None
    try:
        bullet_points = latest_chat.split(SECTIONS_FOR_RESPONSE["bullets"])[-1].split(SECTIONS_FOR_RESPONSE["action_items"])[0].strip()
    except:
        bullet_points = None
    try:
        action_items = latest_chat.split(SECTIONS_FOR_RESPONSE["action_items"])[-1].split(SECTIONS_FOR_RESPONSE["freeform_command"])[0].strip()
    except:
        action_items = None
    try:
        freeform_section = latest_chat.split(SECTIONS_FOR_RESPONSE["freeform_command"])[-1].strip()
    except:
        freeform_section = None

    reponse_model = TextSummarizerResponseModel(
        summary_sentence=summary_sentence,
        bullet_points=bullet_points,
        action_items=action_items,
        freeform_section=freeform_section
    )
    return reponse_model
