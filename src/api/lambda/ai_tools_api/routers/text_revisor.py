import logging
import os
import sys
from typing import List, Optional
from fastapi import APIRouter, Response, status, Request
import openai
from pydantic import conint
import requests
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../utils"))
from utils import initialize_openai, prepare_response, CamelCaseModel, log_to_s3

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


router = APIRouter()

class TextRevisorModel(CamelCaseModel):
    number_of_revisions: Optional[int] = 1
    text_to_revise: str
    revision_types: Optional[List[str]] = ["spelling", "grammar", "sentence structure"]
    tone: Optional[str] = "neutral"
    creativity: Optional[conint (ge=0, le=100)] = 50

class TextRevisorResponseModel(CamelCaseModel):
    revised_text_list: List[str] = [""]


def get_openai_response(prompt: str, instruction: str, num_edits: str="1", creativity: int=50) -> str:
    """
    Method uses openai model text-curie-001 to summarize notes.
    
    The method takes a string of notes and returns a summary of the notes. Optionally, 
    the number of action items and bullets can be specified. The creativity parameter 
    is used to control the temperature of the model. The creativity is 
    divided by 100 and the value is mapped to the range [0.1, 0.75] and is used for the 
    temperature parameter of the request. This method forwards notes with options to 
    openai for processing. The response from openai is then returned to the client.


    :param prompt: Request containing notes and options for summarization.

    :return: response to prompt
    """
    session = requests.session()
    temperature = creativity / 100 * 0.75 + 0.2
    logger.info("temperature: %s", temperature)
    logger.info(f"prompt: {prompt}")
    logger.info(f"instruction: {instruction}")
    logger.info(f"number of edits to generate: {num_edits}")
    data = {
        "model": "text-davinci-edit-001",
        "input": prompt,
        "instruction": instruction,
        "n": int(num_edits),
        "temperature": temperature
    }
    url = "https://api.openai.com/v1/edits"
    initialize_openai()
    headers = {
        'Content-Type': "application/json",
        'Authorization': f"Bearer {openai.api_key}"
    }
    response = session.post(url, headers=headers, json=data).json()
    logger.info(f"openai response: {response}")
    revisions = []
    for choice in response['choices']:
        revisions.append(choice['text'].strip())
    return revisions

@router.post("/text_revisor", response_model=TextRevisorResponseModel, status_code=status.HTTP_200_OK)
async def text_revisor(text_revision_request: TextRevisorModel, request: Request, response: Response):
    """
    Method uses openai model text-davinci-edit-001 to revise text.

    The method takes a string of text and returns a revised version of the text. Optionally, 
    the revision types can be specified. This method forwards text with options to openai for
    processing. The response from openai is then returned to the client.

    :param text_revision_request: Request containing text and options for revision.
    """
    prepare_response(response, request)
    text_revision_request.text_to_revise = text_revision_request.text_to_revise.strip()
    revision_types = text_revision_request.revision_types
    instruction = "Revise text for "
    for revision_type in revision_types[:-1]:
        instruction += revision_type + ", "
    instruction += f"and {revision_types[-1]} and change the tone of the text to be {text_revision_request.tone}."

    response_dict = {
        'revised_text_list': get_openai_response(text_revision_request.text_to_revise, instruction, text_revision_request.number_of_revisions, text_revision_request.creativity)
    }

    response_model = TextRevisorResponseModel(**response_dict)
    logger.info(f"response_model: {response_model}")

    prompts = {
        'text_to_revise': text_revision_request.text_to_revise,
        'instruction': instruction,
        'number_of_revisions': text_revision_request.number_of_revisions,
        'creativity': text_revision_request.creativity
    }
    try:
        await log_to_s3(request, response, response_model, prompts)
    except Exception as e:
        logger.error(f"Error logging to s3: {e}")
    return response_model

