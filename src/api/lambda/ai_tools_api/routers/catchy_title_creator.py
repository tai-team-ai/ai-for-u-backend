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
import logging
import os
import sys
import openai

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../utils"))
from utils import initialize_openai, prepare_response, CamelCaseModel, sanitize_string

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

class CatchyTitleCreatorModel(CamelCaseModel):
    """
    Pydantic model for the request body.
    """
    text: constr(min_length=1, max_length=10000)
    target_audience: constr(min_length=1, max_length=200)
    num_titles: Optional[conint(ge=1, le=10)] = 3
    creativity: Optional[conint(ge=0, le=100)] = 50

class CatchyTitleCreatorResponseModel(CamelCaseModel):
    """
    Pydantic model for the response body.
    """
    titles: List[str] = []

def get_openai_response(prompt: str, num_titles: int, creativity: int=50) -> List[str]:
    """
    Method uses openai model text-davinci-003 to generate catchy titles.

    The prompt is sent to openai for processing. The response from openai is then returned to the client.

    :param prompt: Request containing text, target audience, and number of titles to generate.
    :param num_titles: Number of titles to generate.

    :return: response to prompt
    """
    initialize_openai()
    prompt_len = len(prompt)
    temperature = creativity / 100 * 0.8 + 0.2
    frequency_penalty = 1.5 * (1 - creativity / 100) + 0.5
    presense_penalty = 1.5 * (1 - creativity / 100) + 0.5
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100 * num_titles,
        temperature=int(temperature),
        top_p=1,
        frequency_penalty=frequency_penalty,
        presence_penalty=presense_penalty,
        n=1,
    )
    logger.debug(f"OpenAI response: {response}")
    revisions = []
    for choice in response['choices']:
        revisions.append(choice['text'].strip())
    return revisions

@router.post("/catchy-title-creator", response_model=CatchyTitleCreatorResponseModel, status_code=status.HTTP_200_OK)
async def catchy_title_creator(catchy_title_creator_request: CatchyTitleCreatorModel, response: Response, request: Request):
    """
    Post endpoint for generating catchy titles from a given text.

    :param catchy_title_creator_request: Request containing text, target audience, and number of titles to generate.
    :param response: Response object to add headers to.

    :return: response from openai
    """
    prepare_response(response, request)
    prompt = f"You are a marketer for a company that is trained to write exceptionally catchy titles for text. The "\
        f" text may be any type of content including but not limited to books, articles, blogs, technical articles, "\
            f"video descriptions, etc. I will provide you with the text and a target audience and you will provide a n number of titles "\
                f"that are catchy and easily understood by the target audience with each title wrapped in single quotes. You will only generate titles, nothing else. "\
                    f"The first text and target audience to generate a {catchy_title_creator_request.num_titles} titles for is: "\
                        f"Text:\n'{sanitize_string(catchy_title_creator_request.text)}'\n\nTarget Audience:\n{sanitize_string(catchy_title_creator_request.target_audience)}\n\n"
    response_dict = {
        "titles": get_openai_response(prompt, catchy_title_creator_request.num_titles)
    }

    response_model = CatchyTitleCreatorResponseModel(**response_dict)

    return response_model