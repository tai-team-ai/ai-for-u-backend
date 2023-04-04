from pydantic import constr, conint
from fastapi import APIRouter, Response, status, Request
from typing import Optional, List, Tuple
from pathlib import Path
import logging
import sys

sys.path.append(Path(__file__).parent / "../utils")
from utils import (
    AIToolModel,
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

ENDPOINT_NAME = "email-writer"


@docstring_parameter(ENDPOINT_NAME)
class EmailWriterRequest(BaseTemplateRequest):

    email_recipient: Optional[constr(min_length=1, max_length=30)] = ""
    sender_name: Optional[constr(min_length=1, max_length=30)] = ""
    email_tone: Optional[Tone] = Tone.FORMAL
    word_count_range: Optional[Tuple[conint(ge=1, le=1000), conint(ge=1, le=1000)]] = (100, 200)
    