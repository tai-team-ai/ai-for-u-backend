import logging
import os
from pathlib import Path
import sys
import threading
from typing import Optional
from fastapi import APIRouter, Response, status, Request
import openai

from pydantic import constr, Field


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
)

router = APIRouter()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


MAX_TOKENS_FROM_GPT_RESPONSE = 400

SYSTEM_PROMPT = (
    "You are a professional text summarizer. You job is to summarize the text in markdown format for me in order to help me "
    "understand the text better and allow me to understand the information quickly without having to read the entire text myself. "
    "I may request for a summary sentence, bullet points, and/or actions to be generated from the text."
    "You should only respond with the sections that I specify in my request, nothing else. You should use markdown format "
    "and should use bold titles for each section. By using markdown, you will help me organize the information better."
)

ENDPOINT_NAME = "text-summarizer"


class TextSummarizerRequest(BaseAIInstructionModel):
    """
    **Define the request model for the text summarizer endpoint.**
    
    **Attributes:**
    - text_to_summarize: text for the endpoint to summarize
    - include_summary_sentence: whether or not to include a summary sentence in the response
    - number_of_bullets: number of bullet points to include in the response
    - number_of_action_items: number of action items to include in the response (this is suggested to use with 
        summaries of things such as meeting minutes)
    
    Inherit from BaseAIInstructionModel:    
    """
    __doc__ += BaseAIInstructionModel.__doc__
    text_to_summarize: str = Field(
        ...,
        title="Text to Summarize",
        description="The text that you wanted summarized. (e.g. articles, notes, trnascripts, etc.)",
    )
    include_summary_sentence: Optional[bool] = Field(
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
        default=None,
        title="Number of Action Items",
        description="The number of action items to include in the response. Action items are often applicable for meeting notes, lectures, etc.",
    )



class TextSummarizerResponse(AIToolModel):
    summary: str
    

class TextSummarizerExampleResponse(ExamplesResponse):
    examples: list[TextSummarizerRequest]
    
    
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=TextSummarizerExampleResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> TextSummarizerExampleResponse:
    """Return examples for the text summarizer endpoint."""
    examples = [
        TextSummarizerRequest(
            text_to_summarize="This is a test. This is only a test. This is a test of the emergency broadcast system. ",
            include_summary_sentence=True,
            number_of_bullets=3,
            number_of_action_items=2,
        )
    ]
    response = TextSummarizerExampleResponse(
        example_names=["Example 1"],
        examples=examples
    )
    return response

@router.post(f"/{ENDPOINT_NAME}", response_model=TextSummarizerResponse, responses=error_responses)
async def text_summarizer(text_summarizer_request: TextSummarizerRequest, request: Request):
    """**Summarize text using GPT-3.**"""
    logger.info(f"Received request: {text_summarizer_request}")
    for field_name, value in text_summarizer_request:
        if isinstance(value, str):
            setattr(text_summarizer_request, field_name, value.strip())
    user_prompt = BASE_USER_PROMPT_PREFIX
    if text_summarizer_request.include_summary_sentence:
        user_prompt += f"Please provide me with a summary sentance.\n"
    if text_summarizer_request.number_of_bullets:
        user_prompt += f"Please provide me with {text_summarizer_request.number_of_bullets} bullet points.\n"
    if text_summarizer_request.number_of_action_items:
        user_prompt += f"Please provide me with {text_summarizer_request.number_of_action_items} action items.\n"

    user_prompt += "Finally, here's the text I want you to summarize: " + text_summarizer_request.text_to_summarize

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

    reponse_model = TextSummarizerResponse(
        summary=latest_chat,
    )
    logger.info(f"Returning response for {ENDPOINT_NAME} endpoint.")
    return reponse_model
