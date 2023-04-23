import logging
import os
from pathlib import Path
import sys
import threading
from typing import Optional
from fastapi import APIRouter, Response, status, Request
import openai

from pydantic import conint, Field


sys.path.append(Path(__file__, "../").absolute())
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response
from utils import (
    AIToolModel,
    BaseAIInstructionModel,
    UUID_HEADER_NAME,
    update_user_token_count,
    sanitize_string,
    EXAMPLES_ENDPOINT_POSTFIX,
    ExamplesResponse,
    BASE_USER_PROMPT_PREFIX,
    error_responses,
    TOKEN_EXHAUSTED_JSON_RESPONSE,
    TokensExhaustedException,
    AIToolResponse,
    append_field_prompts_to_prompt,
)
from text_examples import CEO_EMAIL, ARTICLE_EXAMPLE, CLASS_NOTES, TRANSCRIPT_EXAMPLE

router = APIRouter()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


MAX_TOKENS_FROM_GPT_RESPONSE = 400

ENDPOINT_NAME = "text-summarizer"


class TextSummarizerInstructions(BaseAIInstructionModel):
    summary_sentence: Optional[bool] = Field(
        default=True,
        title="Include Summary Sentence",
        description="Whether or not to include a summary sentence in the response.",
    )
    number_of_bullets: Optional[conint(ge=0, le=8)] = Field(
        default=3,
        title="Number of Bullets",
        description="The number of bullet points to include in the response.",
    )
    number_of_action_items: Optional[conint(ge=0, le=8)] = Field(
        title="Number of Action Items",
        description="The number of action items to include in the response. Action items are often applicable for meeting notes, lectures, etc.",
    )

SYSTEM_PROMPT = (
    "You are an expert at summarizing text. You have spent hours "
    "perfecting your summarization skills. You have summarized text for "
    "hundreds of people. Because of your expertise, I want you to summarize "
    "text for me. You should ONLY respond with the summary and nothing else. "
    "I will provide you with a text to summarize and instructions about how to "
    "structure the summary. You should respond with a summary that is tailored "
    "to the instructions. The instructions may ask you to include a summary "
    "sentence, bullet points, or action items. It is important that you "
    "include these if I ask you to. If I don't ask you to include a section, "
    "you should not include it. Remember, you are an expert at summarizing "
    "text. I trust you to summarize text that will be useful to me. Please do "
    "not respond with anything other than the summary."
)

class TextSummarizerRequest(TextSummarizerInstructions):
    text_to_summarize: str = Field(
        ...,
        title="Text to Summarize",
        description="The text that you wanted summarized. (e.g. articles, notes, transcripts, etc.)",
    )

class TextSummarizerExampleResponse(ExamplesResponse):
    examples: list[TextSummarizerRequest]
    
    
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=TextSummarizerExampleResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> TextSummarizerExampleResponse:
    """Return examples for the text summarizer endpoint."""
    examples = [
        TextSummarizerRequest(
            text_to_summarize=CLASS_NOTES,
            include_summary_sentence=True,
            number_of_bullets=5,
            number_of_action_items=2,
        ),
        TextSummarizerRequest(
            text_to_summarize=TRANSCRIPT_EXAMPLE,
            include_summary_sentence=True,
            number_of_bullets=3,
            number_of_action_items=0,
        ),
        TextSummarizerRequest(
            text_to_summarize=ARTICLE_EXAMPLE,
            include_summary_sentence=False,
            number_of_bullets=6,
            number_of_action_items=3,
        ),
        TextSummarizerRequest(
            text_to_summarize=CEO_EMAIL,
            include_summary_sentence=True,
            number_of_bullets=0,
            number_of_action_items=5,
        ),
    ]
    response = TextSummarizerExampleResponse(
        example_names=["Class Notes", "Transcript", "Article", "Email"],
        examples=examples
    )
    return response

@router.post(f"/{ENDPOINT_NAME}", response_model=AIToolResponse, responses=error_responses)
async def text_summarizer(text_summarizer_request: TextSummarizerRequest, request: Request):
    """**Summarize text using GPT-3.**"""
    logger.info(f"Received request: {text_summarizer_request}")
    user_prompt = append_field_prompts_to_prompt(
        TextSummarizerInstructions(**text_summarizer_request.dict()),
        BASE_USER_PROMPT_PREFIX,
    )
    user_prompt += f"\nHere's the text that i want you to summarize for me:\n{text_summarizer_request.text_to_summarize}"
    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=user_prompt
    )
    try:
        chat_session = get_gpt_turbo_response(
            system_prompt=SYSTEM_PROMPT,
            chat_session=GPTTurboChatSession(messages=[user_chat]),
            frequency_penalty=0.0,
            presence_penalty=0.0,
            temperature=0.3,
            uuid=uuid,
            max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE
        )
    except TokensExhaustedException:
        return TOKEN_EXHAUSTED_JSON_RESPONSE

    latest_gpt_chat_model = chat_session.messages[-1]
    update_user_token_count(uuid, latest_gpt_chat_model.token_count)
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)

    response_model = AIToolResponse(
        response=latest_chat,
    )
    logger.info(f"Returning response for {ENDPOINT_NAME} endpoint.")
    return response_model
