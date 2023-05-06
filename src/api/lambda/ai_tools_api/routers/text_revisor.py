import logging
import os
from pathlib import Path
import sys
from typing import List, Optional
from fastapi import APIRouter, Response, status, Request
from enum import Enum
from pydantic import conint, constr, Field
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../utils"))
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../gpt_turbo"))
sys.path.append(Path(__file__).parent / "../text_examples")
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response
from text_examples import SPELLING_ERRORS_EXAMPLE, BADLY_WRITTEN_TRAVEL_BLOG, ARTICLE_EXAMPLE
from utils import (
    AIToolModel,
    EXAMPLES_ENDPOINT_POSTFIX,
    BaseAIInstructionModel,
    docstring_parameter,
    ExamplesResponse,
    Tone,
    AIToolsEndpointName,
    sanitize_string,
    append_field_prompts_to_prompt,
    BASE_USER_PROMPT_PREFIX,
    Tone,
    error_responses,
    TOKENS_EXHAUSTED_LOGIN_JSON_RESPONSE,
    TOKENS_EXHAUSTED_FOR_DAY_JSON_RESPONSE,
    TokensExhaustedException,
)

MAX_TOKENS_FROM_GPT_RESPONSE = 2000


class RevisionType(str, Enum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    SENTENCE_STRUCTURE = "sentence structure"
    WORD_CHOICE = "word choice"
    CONSISTENCY = "consistency"
    PUNCTUATION = "punctuation"


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()
ENDPOINT_NAME = AIToolsEndpointName.TEXT_REVISOR.value

AI_PURPOSE = " ".join(ENDPOINT_NAME.split("-")).lower()
class TextRevisorInstructions(BaseAIInstructionModel):
    revision_types: Optional[list[RevisionType]] = Field(
        default=[revision_type.value for revision_type in RevisionType],
        title="Revision Types",
        description="The types of revisions that you should make to the text. This is helpful if you don't want a ton of changes made to your writing.",
    )
    creativity: Optional[conint(ge=0, le=100)] = Field(
        50,
        title="Creativity (0 = Least Creative, 100 = Most Creative)",
        description="The creativity of the revision. Lower creativity tends to be more similar to the original text while higher creativity tends to be more different from the original text.",
    )
    tone: Optional[Tone] = Field(
        default=Tone.FORMAL,
        title="Tone of the Revision",
        description="The tone that the revised text should have.",
    )


SYSTEM_PROMPT = (
    "You are an expert at revising text. You have spent hours "
    "perfecting your text revision skills. You have revised text for hundreds of people. "
    "Because of your expertise, I want you to revise a text for me. You should ONLY respond "
    "with the revised text and nothing else. I will provide you with a text to revise "
    "and instructions on how to revise the text. You should respond with a revised text "
    "that is tailored to the instructions. The instructions I provide will include "
    "the types of revisions that you should make to the text, the creativity (0 is least creative "
    "while 100 is most creative) of the revised text, and the tone that you should use when "
    "revising the text. When creativity is higher (closer to 100), you have more freedom "
    "to embellish the text. When creativity is lower (closer to 0), you should try to "
    "make the revisions as close to the original text as possible. It is important that "
    "you follow these instructions, especially my instructions for how to revise the text. "
    "As an example: If i ask you to revise for punctuation, you should only revise for punctuation; "
    "If i ask you to revise for spelling, you should only revise for spelling; "
    "If i ask you to revise for multiple things, you should revise for all of them, but nothing else. "
    "I trust you to revise the text in a way that I will like. "
    "Please do not respond with anything other than the revised text."
)

class TextRevisorRequest(TextRevisorInstructions):
    """
    **Define the model for the request body for {0} endpoint.**

    **Attributes:**
    * text_to_revise: The text to revise. This can literally be any block of text.

    **AI Instructions:**

    """
    text_to_revise: constr(min_length=1, max_length=int(MAX_TOKENS_FROM_GPT_RESPONSE * 3 * 0.75)) = Field( # 75 is for 1 token ~= 3 chars, 0.75 is to provide a safety factor in how many tokens is expected from gpt (close to a 1:1 ratio between prompt and response)
        ...,
        title="Text to Revise",
        description="The text to revise. This can literally be any block of text. (e.g. blog post, article, song lyrics, etc.)",
    )

@docstring_parameter(ENDPOINT_NAME)
class TextRevisorResponse(AIToolModel):
    """**Define the model for the response body for the {0} endpoint.**"""
    revised_text: str


@docstring_parameter(ENDPOINT_NAME)
class TextRevisorExamplesResponse(ExamplesResponse):
    """
    **Define examples for the {0} endpoint.**
    
    **Attributes:**
    - examples: A list of TextRevisorRequest objects. Can post these examples to the {0} endpoint without
        modification.
    
    Inherit from ExamplesResponse:
    """
    __doc__ += ExamplesResponse.__doc__
    examples: list[TextRevisorRequest]


@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=TextRevisorExamplesResponse, responses=error_responses)
async def text_revisor_examples():
    """
    **Get examples for the {0} endpoint.**

    This method returns examples for the {0} endpoint. These examples can be posted to the {0} endpoint
    without modification.
    """
    text_revisor_examples = [
        TextRevisorRequest(
            text_to_revise=BADLY_WRITTEN_TRAVEL_BLOG,
            revision_types=[RevisionType.SPELLING, RevisionType.GRAMMAR, RevisionType.SENTENCE_STRUCTURE, RevisionType.WORD_CHOICE, RevisionType.CONSISTENCY, RevisionType.PUNCTUATION],
            tone=Tone.INFORMAL,
            creativity=100,
        ),
        TextRevisorRequest(
            text_to_revise=SPELLING_ERRORS_EXAMPLE,
            revision_types=[RevisionType.SPELLING],
            tone=Tone.ASSERTIVE,
            creativity=20,
        ),
        TextRevisorRequest(
            text_to_revise=ARTICLE_EXAMPLE,
            revision_types=[RevisionType.SENTENCE_STRUCTURE, RevisionType.WORD_CHOICE, RevisionType.CONSISTENCY, RevisionType.PUNCTUATION],
            tone=Tone.ENCOURAGING,
            creativity=50,
        ),
    ]
    example_response = TextRevisorExamplesResponse(
        example_names=["Badly Written", "Spelling Errors", "Word Choice"],
        examples=text_revisor_examples,
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=TextRevisorResponse, status_code=status.HTTP_200_OK)
async def text_revisor(text_revision_request: TextRevisorRequest, request: Request, response: Response):
    """**Revises text using GPT-3.**"""
    logger.info(f"Received request for {ENDPOINT_NAME} endpoint.")
    user_prompt = append_field_prompts_to_prompt(TextRevisorInstructions(**text_revision_request.dict()), BASE_USER_PROMPT_PREFIX)

    user_prompt += f"\nHere is the text that I want you to revise for me: {text_revision_request.text_to_revise}"
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=user_prompt
    )
    temperature = 0.2 + (0.7 * (text_revision_request.creativity / 100))
    try:
        chat_session = get_gpt_turbo_response(
            system_prompt=SYSTEM_PROMPT,
            chat_session=GPTTurboChatSession(messages=[user_chat]),
            frequency_penalty=0.0,
            presence_penalty=0.0,
            temperature=temperature,
            max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE,
        )
    except TokensExhaustedException as e:
        if e.login:
            return TOKENS_EXHAUSTED_LOGIN_JSON_RESPONSE
        return TOKENS_EXHAUSTED_FOR_DAY_JSON_RESPONSE

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_chat = latest_gpt_chat_model.content

    revised_text = sanitize_string(latest_chat)
    response_model = TextRevisorResponse(
        revised_text=revised_text
    )
    logger.info(f"Returning response for {ENDPOINT_NAME} endpoint.")
    return response_model
