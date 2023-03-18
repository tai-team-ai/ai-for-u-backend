import logging
import os
import sys
from typing import List, Optional
from fastapi import APIRouter, Response, status, Request
from enum import Enum
from pydantic import conint
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../utils"))
from utils import CamelCaseModel, EXAMPLES_ENDPOINT_POSTFIX, docstring_parameter

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


router = APIRouter()

ENDPOINT_NAME = "text-revisor"

class RevisionType(Enum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    SENTENCE_STRUCTURE = "sentence structure"
    WORD_CHOICE = "word choice"
    CONSISTENCY = "consistency"
    PUNCTUATION = "punctuation"


class Tone(Enum):
    FORMAL = "formal"
    INFORMAL = "informal"
    OPTIMISTIC = "optimistic"
    WORRIED = "worried"
    FRIENDLY = "friendly"
    CURIOUS = "curious"
    ASSERTIVE = "assertive"
    ENCOURAGING = "encouraging"
    SURPRISED = "surprised"
    COOPERATIVE = "cooperative"


@docstring_parameter(ENDPOINT_NAME)
class TextRevisorRequest(CamelCaseModel):
    """
    Define the model for the request body for {0} endpoint.
    
    
    """
    text_to_revise: str
    number_of_revisions: Optional[int] = 1
    revision_types: Optional[List[str]] = ["spelling", "grammar", "sentence structure"]
    tone: Optional[str] = "neutral"
    creativity: Optional[conint (ge=0, le=100)] = 50


class TextRevisorResponse(CamelCaseModel):
    revised_text_list: List[str] = [""]


@router.post("/text_revisor", response_model=TextRevisorResponse, status_code=status.HTTP_200_OK)
async def text_revisor(text_revision_request: TextRevisorRequest, request: Request, response: Response):
    """
    Method uses openai model text-davinci-edit-001 to revise text.

    The method takes a string of text and returns a revised version of the text. Optionally, 
    the revision types can be specified. This method forwards text with options to openai for
    processing. The response from openai is then returned to the client.

    :param text_revision_request: Request containing text and options for revision.
    """
    return TextRevisorResponse()

