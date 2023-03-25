"""Define a fastapi router for the feedback endpoint."""
from enum import Enum
import sys
from typing import Optional, List
from pathlib import Path
from pydantic import constr
from loguru import logger
from fastapi import APIRouter, Request, Response, status
sys.path.append(Path(__file__).parent / "../utils")
from utils import (
    AIToolModel,
    sanitize_string,
    docstring_parameter,
)


router = APIRouter()

ENDPOINT_NAME = "feedback"


class Rating(Enum):
    """Define the possible rating values."""
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"


@docstring_parameter(ENDPOINT_NAME)
class FeedbackRequest(AIToolModel):
    """
    **Define the model for the request body for the {0} endpoint.**

    **Atrributes:**
    - user_prompt_feedback_context: The context of the user prompt that the feedback is for.
        Any of the AI tool request models can be used here. (templates or sandbox)
    - ai_response_feedback_context: The context of the AI response that the feedback is for.
        This is the response from the AI tool.
    - star_rating: The star rating left by the user.
    - written_feedback: Any written feedback left by the user.
    """
    user_prompt_feedback_context: AIToolModel
    ai_response_feedback_context: AIToolModel
    star_rating: Rating
    written_feedback: constr(min_length=0, max_length=500) = ""


@docstring_parameter(ENDPOINT_NAME)
@router.post(f"/{ENDPOINT_NAME}", status_code=status.HTTP_200_OK)
async def feedback(response: Response, feedback_request: FeedbackRequest):
    """
    **POST feedback to the {0} endpoint.**

    This method is used to record user feedback for the AI tools. This method 
    returns an empty response with a 200 status code if the feedback is logged 
    successfully.
    """
    logger.info(f"Received request for {ENDPOINT_NAME} endpoint.")
    logger.info(f"Request body: {feedback_request.json()}")
    return response
