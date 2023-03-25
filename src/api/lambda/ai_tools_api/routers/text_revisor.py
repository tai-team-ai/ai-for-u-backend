import logging
import os
import sys
from typing import List, Optional
from fastapi import APIRouter, Response, status, Request
from enum import Enum
from pydantic import conint
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../utils"))
from utils import (
    CamelCaseModel,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    BaseTemplateRequest,
    ExamplesResponse,
    Tone
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


router = APIRouter()

ENDPOINT_NAME = "text-revisor"

class RevisionType(str, Enum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    SENTENCE_STRUCTURE = "sentence structure"
    WORD_CHOICE = "word choice"
    CONSISTENCY = "consistency"
    PUNCTUATION = "punctuation"


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
class TextRevisorResponse(CamelCaseModel):
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
    response = TextRevisorResponse(
        revised_text_list=[
            "This is a revised text that is probably much better than the original text.",
            "This is a revised text that is probably much better than the original text.",
    )
    return response

