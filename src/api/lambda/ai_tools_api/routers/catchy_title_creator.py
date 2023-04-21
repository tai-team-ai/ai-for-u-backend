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

from pydantic import constr, conint, Field
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
    UUID_HEADER_NAME,
    append_field_prompts_to_prompt,
    BASE_USER_PROMPT_PREFIX,
    error_responses,
    TOKEN_EXHAUSTED_JSON_RESPONSE,
    TokensExhaustedException,
    AIToolResponse,
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.CATCHY_TITLE_CREATOR.value
MAX_TOKENS_FROM_GPT_RESPONSE = 200

AI_PURPOSE = " ".join(ENDPOINT_NAME.split("-")).lower()
@docstring_parameter(AI_PURPOSE, [tone.value for tone in Tone])
class CatchyTitleCreatorInstructions(BaseAIInstructionModel):
    """You are an expert {0}. I will provide a text and should respond with a list of catchy titles in markdown format, nothing else.
    
    I will provide instructions for you to follow to help you generate the titles. These instructions should be followed exactly in order to generate the best titles that you can and that i like.

    For each title, only respond with the title, nothing else. You should use markdown format when returning the titles and should return them as a list.
    
    **Instructions that I may provide you in order to assist you in creating the titles for me:**
    * type_of_title: This can literally be anything. (eg. book, company, coffee shop, song, documentary, social media post, etc.)
    * target_audience: The target audience for the title (eg. children, adults, teenagers, public, superiors, etc.)
    * tone: The expected tone of the titles you should generate. Here are the possible tones: {1}.
    * specific_keywords_to_include: A list of specific keywords that you should include in the titles. These can help your title perform better for SEO (e.g. 'how to', 'best', 'top', 'ultimate', 'ultimate guide', etc.).
    * num_titles: The number of titles to generate (As instructed above, please use markdown format when returning the titles as a list).
    * creativity: The creativity of the titles. Where 0 is the least creative and 100 is the most creative. More creativity may be more inspiring but less accurate while less creativity may be more accurate but less inspiring.
    * text_or_description: The text or description of what you are generating catchy titles for. For generating titles for text (e.g. books, articles, blogs, social media posts, songs, etc.), this should probably be the text. For other types of things, (e.g. coffee shop, company name, etc.) this should be a description of the thing you are generating catchy titles for.
    """
    type_of_title: Optional[constr(min_length=1, max_length=50)] = Field(
        ...,
        title="What's the Title For?",
        description="This can literally be anything. (eg. book, company, coffee shop, song, documentary, social media post, etc.)"
    )
    target_audience: Optional[constr(min_length=1, max_length=200)] = Field(
        ...,
        title="Target Audience",
        description="The target audience for the title (e.g. children, adults, teenagers, public, superiors, etc.)"
    )
    tone: Optional[Tone] = Field(
        default=Tone.INFORMAL,
        title="Tone",
        description="The expected tone of the generated titles."
    )
    specific_keywords_to_include: Optional[List[constr(min_length=1, max_length=20)]] = Field(
        default=[],
        title="Keywords to Include in Titles",
        description="These can help your title perform better for SEO (e.g. 'how to', 'best', 'top', 'ultimate', 'ultimate guide', etc.)."
    )
    num_titles: Optional[conint(ge=1, le=10)] = Field(
        default=3,
        title="Number of Titles to Create",
        description="The number of titles that you want to generate."
    )
    creativity: Optional[conint(ge=0, le=100)] = Field(
        50,
        title="Creativity (0 = Least Creative, 100 = Most Creative)",
        description="The creativity of the titles. More creativity may be more inspiring but less accurate while less creativity may be more accurate but less inspiring."
    )

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
    text_or_description: constr(min_length=1, max_length=10000) = Field(
        ...,
        title="Description of What you are Generating Titles for (if generating titles for something written, this should be the text)",
        description="This can be the text you are generating titles for, or if you are generating titles for something else, you can describe what you are generating titles for. Example -> Coffee Shop, Company Name, etc."
    )


@docstring_parameter(ENDPOINT_NAME)
class CatchyTitleCreatorExamplesResponse(ExamplesResponse):
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
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=CatchyTitleCreatorExamplesResponse, status_code=status.HTTP_200_OK)
async def catchy_title_creator_examples():
    """
    **Get examples for the {0} endpoint.**
    
    This method returns a list of examples for the {0} endpoint. These examples can be posted to the {0} endpoint 
    without modification.
    """
    catchy_title_example = CatchyTitleCreatorRequest(
        text_or_description="This is an amazing text that I wrote. It is so amazing that I am going to write a catchy title for it.",
        target_audience="My boss",
        tone=Tone.FRIENDLY,
        num_titles=8,
        creativity=100,
        specific_keywords_to_include=["Best Title Ever", "Amazing Title", "Catchy Title"],
        type_of_title="Coffee Shop Name",
    )
    example_response = CatchyTitleCreatorExamplesResponse(
        example_names=["Catchy Title Example"],
        examples=[catchy_title_example]
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=AIToolResponse, responses=error_responses)
async def catchy_title_creator(catchy_title_creator_request: CatchyTitleCreatorRequest, response: Response, request: Request):
    """**Generate catchy titles using GPT-3.**"""
    logger.info(f"Received request for {ENDPOINT_NAME} endpoint.")
    user_prompt = append_field_prompts_to_prompt(CatchyTitleCreatorInstructions(**catchy_title_creator_request.dict()), BASE_USER_PROMPT_PREFIX)

    user_prompt += f"\nHere is the text/description of what you should create catchy titles for: {catchy_title_creator_request.text_or_description}"
    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=user_prompt,
    )
    try:
        chat_session = get_gpt_turbo_response(
            system_prompt=SYSTEM_PROMPT,
            chat_session=GPTTurboChatSession(messages=[user_chat]),
            frequency_penalty=0.0,
            presence_penalty=0.0,
            temperature=0.3,
            uuid=uuid,
            max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE,
        )
    except TokensExhaustedException:
        return TOKEN_EXHAUSTED_JSON_RESPONSE

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_chat = latest_gpt_chat_model.content
    logger.info("Latest chat: %s", latest_chat)
    latest_chat = sanitize_string(latest_chat)

    response_model = AIToolResponse(response=latest_chat)
    logger.info("Returning response: %s", response_model)
    return response_model
