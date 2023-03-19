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
import os
import sys
import openai

sys.path.append(Path(__file__).parent / "../utils")
from utils import (
    CamelCaseModel,
    sanitize_string,
    BaseTemplateRequest,
    Tone,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = "catchy-title-creator"


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


    Inherit from BaseRequest:
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
class CatchyTitleCreatorResponse(CamelCaseModel):
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
    prompt = f"You are a marketer for a company that is trained to write exceptionally catchy titles for text. The "\
        f" text may be any type of content including but not limited to books, articles, blogs, technical articles, "\
            f"video descriptions, etc. I will provide you with the text and a target audience and you will provide a n number of titles "\
                f"that are catchy and easily understood by the target audience with each title wrapped in single quotes. You will only generate titles, nothing else. "\
                    f"The first text and target audience to generate a {catchy_title_creator_request.num_titles} titles for is: "\
                        f"Text:\n'{sanitize_string(catchy_title_creator_request.text)}'\n\nTarget Audience:\n{sanitize_string(catchy_title_creator_request.target_audience)}\n\n"
    return CatchyTitleCreatorResponse(titles=["Test Title 1", "Test Title 2", "Test Title 3"])