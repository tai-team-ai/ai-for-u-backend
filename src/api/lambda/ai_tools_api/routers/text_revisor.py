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
    UUID_HEADER_NAME,
    sanitize_string,
    append_field_prompts_to_prompt,
    BASE_USER_PROMPT_PREFIX,
    Tone,
    error_responses,
    TOKEN_EXHAUSTED_JSON_RESPONSE,
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
@docstring_parameter(AI_PURPOSE, [revision_type.value for revision_type in RevisionType], [tone.value for tone in Tone])
class TextRevisorInstructions(BaseAIInstructionModel):
    """You are an expert {0}. I will provide a text to revise and should respond with a revised version of that text, nothing else.

    For each revision, only respond with the revision, nothing else (no explanations, not the original text, no comparisons between the original and the revised, etc.).
    I will also provide a list of instructions that you should follow when revising the text to help you make the bets revision possible that i like.

    **Instructions that I may provide you to assist you in how you revise the text:**
    * revision_types: The types of revisions that you should make to the text. The types of revisions that can be made are: {1}. Use this list as a guide to what types of revisions you should make. Do NOT revise the text in ways that I do not prescribe.
    * creativity: The creativity of the revised text. Where 0 is the least creative and 100 is the most creative. Further, a creativity closer to 0 signifies that the revisions should be made in a way that is as close to the original text as possible while a creativity closer to 100 signifies that you have more freedom to elaborate on the original text.
    * tone: The tone that you should use when revising the text. Here are the possible tones: {2}.
    * text_to_revise: The text to revise. This can literally be any block of text. I guarantee that I will provide this text.
    """
    revision_types: Optional[list[RevisionType]] = Field(
        default=[revision_type.value for revision_type in RevisionType],
        title="Revision Types",
        description="The types of revisions that you should make to the text. This is helpful if you don't want a ton of changes made to your writing.",
    )
    creativity: Optional[conint(ge=0, le=100)] = Field(
        50,
        title="Creativity (0 = Least Creative, 100 = Most Creative)",
        description="The creativity of the revision. More creativity tends to be more similar to the original text while less creativity tends to be more similar to the original text.",
    )
    tone: Optional[Tone] = Field(
        default=Tone.FORMAL,
        title="Tone of the Revision",
        description="The tone used when making the revisions to the text.",
    )

SYSTEM_PROMPT = TextRevisorInstructions.__doc__

@docstring_parameter(ENDPOINT_NAME)
class TextRevisorRequest(TextRevisorInstructions):
    """
    **Define the model for the request body for {0} endpoint.**

    **Attributes:**
    * text_to_revise: The text to revise. This can literally be any block of text.

    **AI Instructions:**

    """
    __doc__ += TextRevisorInstructions.__doc__
    text_to_revise: constr(min_length=1, max_length=int(MAX_TOKENS_FROM_GPT_RESPONSE * 0.75 * 0.75)) = Field( # first 0.75 accounts for 1 token being about 3/4 a word, second is to provide a safety factor in how many tokens is expected from gpt (close to a 1:1 ratio between prompt and response)
        ...,
        title="Text to Revise",
        description="The text to revise. This can literally be any block of text. (e.g. blog post, article, song lyrics, etc.)",
    )

@docstring_parameter(ENDPOINT_NAME)
class TextRevisorResponse(AIToolModel):
    """**Define the model for the response body for the {0} endpoint.**"""
    revised_text_list: List[str] = []


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


@docstring_parameter(ENDPOINT_NAME)
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

    user_prompt += f"\nHere is the text you should revise: {text_revision_request.text_to_revise}"
    uuid = request.headers.get(UUID_HEADER_NAME)
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
            uuid=uuid,
            max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE,
        )
    except TokensExhaustedException:
        return TOKEN_EXHAUSTED_JSON_RESPONSE

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_chat = latest_gpt_chat_model.content

    revised_text_list = [sanitize_string(latest_chat)]
    response_model = TextRevisorResponse(
        revised_text_list=revised_text_list
    )
    logger.info(f"Returning response for {ENDPOINT_NAME} endpoint.")
    return response_model
