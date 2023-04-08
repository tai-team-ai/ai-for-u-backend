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
    BaseAIInstructionModel,
    Tone,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse,
    AIToolsEndpointName,
    update_user_token_count,
    UUID_HEADER_NAME,
    append_field_prompts_to_prompt,
    BASE_USER_PROMPT_PREFIX,
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.CATCHY_TITLE_CREATOR.value
MAX_TOKENS_FROM_GPT_RESPONSE = 200
TITLE_RESPONSE_PREFIX = "Generated Title:: "

AI_PURPOSE = " ".join(ENDPOINT_NAME.split("-")).lower()
@docstring_parameter(AI_PURPOSE, TITLE_RESPONSE_PREFIX, [tone.value for tone in Tone])
class CatchyTitleCreatorInstructions(BaseAIInstructionModel):
    """You are an expert {0}. I will provide a text and should respond with a list of catchy titles for that text, nothing else.

    For each title, only respond with the title, nothing else. For each title you should prefix each title with the string '{1}' to differentiate between the titles.
    
    **Instructions that I may provide you:**
    * text_type: The type of text to generate a catchy title for (eg. book, article, song, documentary, public, social media post, etc.)
    * target_audience: The target audience for the text (eg. children, adults, teenagers, public, superiors, etc.)
    * tone: The expected tone of the titles you should generate. Here are the possible tones: {2}.
    * specific_keywords_to_include: A list of specific keywords that you should include in every title that you generate.
    * num_titles: The number of titles to generate (As instructed above, prefix each title with the string '{1}' to differentiate between the titles).
    * creativity: The creativity of the titles. Where 0 is the least creative and 100 is the most creative. Further, a creativity closer to 0 signifies that the titles should be made in a way that is as close to the original text as possible while a creativity closer to 100 signifies that you have more freedom to embellish the text.
    """
    text_type: Optional[constr(min_length=1, max_length=50)] = "document"
    target_audience: Optional[constr(min_length=1, max_length=200)] = "public"
    tone: Optional[Tone] = Tone.INFORMAL
    specific_keywords_to_include: Optional[list[constr(min_length=1, max_length=20)]] = []
    num_titles: Optional[conint(ge=1, le=10)] = 3
    creativity: Optional[conint(ge=0, le=100)] = 50

SYSTEM_PROMPT = CatchyTitleCreatorInstructions.__doc__

@docstring_parameter(ENDPOINT_NAME)
class CatchyTitleCreatorRequest(CatchyTitleCreatorInstructions):
    """
    **Define the model for the request body for {0} endpoint.**
    
    **Atrributes:**
    - text: The text to generate a catchy title for.

    **AI Instructions:**

    """

    __doc__ += BaseAIInstructionModel.__doc__
    text: constr(min_length=1, max_length=10000)



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
        tone=Tone.FRIENDLY,
        num_titles=8,
        creativity=100,
        specific_keywords_to_include=["Best Title Ever", "Amazing Title", "Catchy Title"],
        text_type="document",
    )
    example_response = CatchyTitleCreatorExamplesReponse(
        example_names=["Catchy Title Example"],
        examples=[catchy_title_example]
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=CatchyTitleCreatorResponse, status_code=status.HTTP_200_OK)
async def catchy_title_creator(catchy_title_creator_request: CatchyTitleCreatorRequest, response: Response, request: Request):
    """**Generate catchy titles using GPT-3.**"""
    logger.info(f"Received request for {ENDPOINT_NAME} endpoint.")
    user_prompt = append_field_prompts_to_prompt(CatchyTitleCreatorInstructions(**catchy_title_creator_request.dict()), BASE_USER_PROMPT_PREFIX)

    user_prompt += f"\nHere is the text you should create catchy titles for: {catchy_title_creator_request.text}"
    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=user_prompt,
    )
    chat_session = get_gpt_turbo_response(
        system_prompt=SYSTEM_PROMPT,
        chat_session=GPTTurboChatSession(messages=[user_chat]),
        frequency_penalty=0.0,
        presence_penalty=0.0,
        temperature=0.3,
        uuid=uuid,
        max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE,
    )

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_chat = latest_gpt_chat_model.content
    logger.info("Latest chat: %s", latest_chat)
    latest_chat = sanitize_string(latest_chat)

    titles = latest_chat.split(TITLE_RESPONSE_PREFIX)
    titles = [title.strip() for title in titles if title.strip()]

    response_model = CatchyTitleCreatorResponse(titles=titles)
    logger.info("Returning response: %s", response_model)
    return response_model