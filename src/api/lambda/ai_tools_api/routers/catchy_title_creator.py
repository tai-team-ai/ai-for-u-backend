"""
Module for the catchy title creator endpoint.

This endpoint uses the OpenAI API to generate a catchy title for a given text 
provided by the user. The endpoint takes a text, target audience for title, and a number of titles to generate. The endpoint
then constructs a prompt with this data and sends it to the OpenAI API. The response from the API is then returned to the 
client. 

Attributes:
    router (APIRouter): Router for the catchy title creator endpoint.
    CatchyTitleCreatorModel (Pydantic Model): Pydantic model for the request body.
    CatchyTitleCreatorResponseModel (Pydantic Model): Pydantic model for the response body.
    get_openai_response (function): Method to get response from openai.
    catchy_title_creator (function): Post endpoint for the lambda function.
"""

from pydantic import constr, conint
from fastapi import APIRouter, Response, status, Request
from typing import Optional, List
from pathlib import Path
import logging
import sys
import os

sys.path.append(Path(__file__).parent / "../utils")
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../gpt_turbo"))
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response
from utils import (
    AIToolModel,
    sanitize_string,
    BaseTemplateRequest,
    Tone,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse,
    AIToolsEndpointName,
    update_user_token_count,
    UUID_HEADER_NAME,
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.CATCHY_TITLE_CREATOR.value

KEYWORDS_FOR_PROMPT = {
    "text_type": "Text Type",
    "target_audience": "Target Audience",
    "expected_tone": "Expected Tone",
    "specific_keywords": "Specific Keywords that MUST be Included",
    "num_titles": "Number of Titles to Generate",
    "creativity": "Creativity",
}

TITLE_RESPONSE_PREFIX = "Title: "

SYSTEM_PROMPT = (
    "As an AI catchy title generator, create engaging titles for the user's text based on their input. "
    f"Consider the provided {KEYWORDS_FOR_PROMPT['text']}, {KEYWORDS_FOR_PROMPT['text_type']}, {KEYWORDS_FOR_PROMPT['target_audience']}, "
    f"and {KEYWORDS_FOR_PROMPT['expected_tone']}. Include the {KEYWORDS_FOR_PROMPT['specific_keywords']} that MUST be incorporated in the titles. "
    "Generate the requested {KEYWORDS_FOR_PROMPT['num_titles']} number of titles, using the specified {KEYWORDS_FOR_PROMPT['creativity']} level. "
    "When not provided, assume a creativity level of 50 (0 least creative, 100 most creative). "
    "Create distinct and attractive titles that capture the essence of the text and appeal to the target audience. "
    "Present the generated titles as a list, using the prefix '{TITLE_RESPONSE_PREFIX}' to differentiate between them."
)


@docstring_parameter(ENDPOINT_NAME)
class CatchyTitleCreatorRequest(BaseTemplateRequest):
    """
    **Define the model for the request body for {0} endpoint.**
    
    **Atrributes:**
    - text: The text to generate a catchy title for.
    - text_type: The type of text to generate a catchy title for (eg. book, article, song, documentary, etc.)
    - target_audience: The target audience for the title (eg. students, teachers, my boss, public, etc.)
    - expected_tone: The expected tone of the titles; defined by the Tone enum
    - specific_keywords_to_include: Specific keywords to include in the title (eg. "Penguins", "The Great Gatsby", etc.)
    - num_titles: The number of titles to generate for the text
    - creativity: The creativity of the title; where 0 is the least creative and 100 is the most creative


    Inherit from BaseTemplateRequest:
    """

    __doc__ += BaseTemplateRequest.__doc__
    text: constr(min_length=1, max_length=10000)
    text_type: Optional[constr(min_length=1, max_length=50)] = "document"
    target_audience: Optional[constr(min_length=1, max_length=200)] = "public"
    expected_tone: Optional[Tone] = Tone.INFORMAL
    specific_keywords_to_include: Optional[list[constr(min_length=1, max_length=20)]] = []
    num_titles: Optional[conint(ge=1, le=10)] = 3
    creativity: Optional[conint(ge=0, le=100)] = 50


@docstring_parameter(ENDPOINT_NAME)
class CatchyTitleCreatorResponse(AIToolModel):
    """
    **Define the model for the response body for {0} endpoint.**
    
    **Atrributes:**
    - titles: The list of titles generated for the text. They are not in any particular order.
    """
    titles: List[str] = []


@docstring_parameter(ENDPOINT_NAME)
class CatchyTitleCreatorExamplesReponse(ExamplesResponse):
    """
    **Define examples for teh {0} endpoint.**
    
    **Atrributes:**
    - examples: List of examples for the {0} endpoint. Can post these examples to the {0} endpoint without
        modification.
    
    Inherit from ExamplesResponse:
    """
    __doc__ += ExamplesResponse.__doc__
    examples: list[CatchyTitleCreatorRequest]

@docstring_parameter(ENDPOINT_NAME)
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=CatchyTitleCreatorExamplesReponse, status_code=status.HTTP_200_OK)
async def catchy_title_creator_examples():
    """
    **Get examples for the {0} endpoint.**
    
    This method returns a list of examples for the {0} endpoint. These examples can be posted to the {0} endpoint 
    without modification.
    """
    catchy_title_example = CatchyTitleCreatorRequest(
        text="This is an amazing text that I wrote. It is so amazing that I am going to write a catchy title for it.",
        target_audience="My boss",
        expected_tone=Tone.WORRIED,
        num_titles=8,
        creativity=100,
        specific_keywords_to_include=["Best Title Ever", "Amazing Title", "Catchy Title"],
        text_type="document",
        freeform_command="The titles all should be less than 50 characters long."
    )
    example_response = CatchyTitleCreatorExamplesReponse(
        example_names=["Catchy Title Example"],
        examples=[catchy_title_example]
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=CatchyTitleCreatorResponse, status_code=status.HTTP_200_OK)
async def catchy_title_creator(catchy_title_creator_request: CatchyTitleCreatorRequest, response: Response, request: Request):
    """
    Post endpoint for generating catchy titles from a given text.

    :param catchy_title_creator_request: Request containing text, target audience, and number of titles to generate.
    :param response: Response object to add headers to.

    :return: response from openai
    """

    system_prompt = SYSTEM_PROMPT
    system_prompt += f"{KEYWORDS_FOR_PROMPT['text_type']}: {catchy_title_creator_request.text_type}. "
    system_prompt += f"{KEYWORDS_FOR_PROMPT['target_audience']}: {catchy_title_creator_request.target_audience}. "
    system_prompt += f"{KEYWORDS_FOR_PROMPT['expected_tone']}: {catchy_title_creator_request.expected_tone.value}. "
    system_prompt += f"{KEYWORDS_FOR_PROMPT['specific_keywords']}: {', '.join(catchy_title_creator_request.specific_keywords)}. "

    system_prompt += "Finally, here's the text I want you to summarize: "

    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=catchy_title_creator_request.text,
    )
    chat_session = get_gpt_turbo_response(
        system_prompt=system_prompt,
        chat_session=GPTTurboChatSession(messages=[user_chat]),
        frequency_penalty=0.0,
        presence_penalty=0.0,
        temperature=0.3,
        uuid=uuid,
        max_tokens=MAX_TOKENS
    )

    latest_gpt_chat_model = chat_session.messages[-1]
    update_user_token_count(uuid, latest_gpt_chat_model.token_count)
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)

    titles = latest_chat.split("'")[1::2]

    response_model = CatchyTitleCreatorResponse(titles=titles)
    return response_model