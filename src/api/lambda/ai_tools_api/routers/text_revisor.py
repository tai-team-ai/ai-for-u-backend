import logging
import os
import sys
from typing import List, Optional
from fastapi import APIRouter, Response, status, Request
from enum import Enum
from pydantic import conint
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../utils"))
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../gpt_turbo"))
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response
from utils import (
    AIToolModel,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    BaseTemplateRequest,
    ExamplesResponse,
    Tone,
    AIToolsEndpointName,
    UUID_HEADER_NAME,
    update_user_token_count,
    sanitize_string,
)

MAX_TOKENS = 400


class RevisionType(str, Enum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    SENTENCE_STRUCTURE = "sentence structure"
    WORD_CHOICE = "word choice"
    CONSISTENCY = "consistency"
    PUNCTUATION = "punctuation"

REVISION_RESPONSE_PREFIX = "Revision: "

SYSTEM_PROMPT = (
    "As an AI text revisor, revise the provided text considering specific fields the user may include in their request: "
    f"{RevisionType.SPELLING}, {RevisionType.GRAMMAR}, {RevisionType.SENTENCE_STRUCTURE}, "
    f"{RevisionType.WORD_CHOICE}, {RevisionType.CONSISTENCY}, and {RevisionType.PUNCTUATION}. "
    "The user may also specify the number of revisions, the tone, and the creativity level of the revised text. "
    "When not provided, assume a friendly tone and a creativity level of 50 (0 least creative, 100 most creative). "
    "At a creativity level of 0, do not change the meaning of the text, while at a creativity level of 100, feel free to embellish the text. "
    "For each revision, adhere to the user's preferences and requirements while maintaining the original meaning and intent of the text. "
    "Present the revised text as a list, using the prefix '{REVISION_RESPONSE_PREFIX}' to differentiate between revisions. "
    "Provide distinct alternatives when multiple revisions are requested, always focusing on improving the text according to the specified fields."
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.TEXT_REVISOR.value

KEYWORDS_FOR_PROMPT = {
    "revision_types": "Revision Types",
    "tone": "Tone",
    "creativity": "Creativity",
    "freeform_command": "Freeform Command",
    "text_to_revise": "Text to Revise"
}


@docstring_parameter(ENDPOINT_NAME)
class TextRevisorRequest(BaseTemplateRequest):
    """
    **Define the model for the request body for {0} endpoint.**
    
    **Attributes:**
    - text_to_revise: The text to revise. This can literally be any block of text.
    - number_of_revisions: The number of revisions to return in the response.
    - revision_types: The types of revisions to make.
    - tone: The tone that the revised text should have.
    - creativity: The creativity of the revised text. Where 0 is the least creative and 100 is the most creative.
    
    Inherit from BaseRequest:
    """
    __doc__ += BaseTemplateRequest.__doc__
    text_to_revise: str
    number_of_revisions: Optional[int] = 1
    revision_types: Optional[list[RevisionType]] = [revision_type for revision_type in RevisionType]
    tone: Optional[Tone] = Tone.FRIENDLY
    creativity: Optional[conint (ge=0, le=100)] = 50


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
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=TextRevisorExamplesResponse, status_code=status.HTTP_200_OK)
async def text_revisor_examples():
    """
    **Get examples for the {0} endpoint.**

    This method returns examples for the {0} endpoint. These examples can be posted to the {0} endpoint
    without modification.
    """
    text_revisor_example = TextRevisorRequest(
        text_to_revise="This are some porrly written text. Its probaly needing to be revised in order to help it sound much more better.",
        number_of_revisions=4,
        revision_types=[RevisionType.SPELLING, RevisionType.GRAMMAR, RevisionType.SENTENCE_STRUCTURE, RevisionType.WORD_CHOICE, RevisionType.CONSISTENCY, RevisionType.PUNCTUATION],
        tone=Tone.ASSERTIVE,
        creativity=100,
        freeform_command="The revised text should be combined into one sentence.",
    )
    example_response = TextRevisorExamplesResponse(
        example_names=["Badly Written Text"],
        examples=[text_revisor_example],
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=TextRevisorResponse, status_code=status.HTTP_200_OK)
async def text_revisor(text_revision_request: TextRevisorRequest, request: Request, response: Response):
    """
    Method uses openai model text-davinci-edit-001 to revise text.

    The method takes a string of text and returns a revised version of the text. Optionally, 
    the revision types can be specified. This method forwards text with options to openai for
    processing. The response from openai is then returned to the client.

    :param text_revision_request: Request containing text and options for revision.
    """
    system_prompt = SYSTEM_PROMPT
    system_prompt += f"{KEYWORDS_FOR_PROMPT['revision_types']}: {', '.join([rt.value for rt in text_revision_request.revision_types])}. "
    system_prompt += f"{KEYWORDS_FOR_PROMPT['tone']}: {text_revision_request.tone.value}. "
    system_prompt += f"{KEYWORDS_FOR_PROMPT['creativity']}: {text_revision_request.creativity}. "
    if text_revision_request.freeform_command:
        system_prompt += f"{KEYWORDS_FOR_PROMPT['freeform_command']}: {text_revision_request.freeform_command}. "
    system_prompt += f"{KEYWORDS_FOR_PROMPT['text_to_revise']}: "

    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=text_revision_request.text_to_revise
    )
    temperature = 0.2 + (0.7 * (text_revision_request.creativity / 100))
    chat_session = get_gpt_turbo_response(
        system_prompt=system_prompt,
        chat_session=GPTTurboChatSession(messages=[user_chat]),
        frequency_penalty=0.0,
        presence_penalty=0.0,
        temperature=temperature,
        uuid=uuid,
        max_tokens=MAX_TOKENS
    )

    latest_gpt_chat_model = chat_session.messages[-1]
    update_user_token_count(uuid, latest_gpt_chat_model.token_count)
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)

    revised_text_list = latest_chat.split("\n")
    revised_text_list = [text.strip() for text in revised_text_list if text.strip()]

    response_model = TextRevisorResponse(
        revised_text_list=revised_text_list
    )
    return response_model
