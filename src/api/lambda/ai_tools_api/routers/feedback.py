"""Define a fastapi router for the feedback endpoint."""
from enum import Enum
import sys
from typing import Optional, List
from pathlib import Path
from uuid import uuid4
from pydantic import constr
from loguru import logger
from fastapi import APIRouter, Request, Response, status
from catchy_title_creator import CatchyTitleCreatorRequest, CatchyTitleCreatorResponse
from cover_letter_writer import CoverLetterWriterRequest, CoverLetterWriterResponse
from sandbox_chatgpt import SandBoxChatGPTRequest, SandBoxChatGPTResponse
from text_revisor import TextRevisorRequest, TextRevisorResponse
from text_summarizer import TextSummarizerRequest, TextSummarizerResponse


sys.path.append(Path(__file__, "../dynamodb_models"))
sys.path.append(Path(__file__).parent / "../utils")
from utils import (
    AIToolModel,
    docstring_parameter,
    AIToolsEndpointName,
    UUID_HEADER_NAME,
)
from dynamodb_models import FeedbackTableModel


router = APIRouter()

ENDPOINT_NAME = "feedback"

class Rating(str, Enum):
    """Define the possible rating values."""
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class SupportedRequest(str, Enum):
    """Define the possible request types that can be given feedback on."""
    CATCHY_TITLE_CREATOR = CatchyTitleCreatorRequest
    COVER_LETTER_WRITER = CoverLetterWriterRequest
    SANDBOX_CHATGPT = SandBoxChatGPTRequest
    TEXT_REVISOR = TextRevisorRequest
    TEXT_SUMMARIZER = TextSummarizerRequest


class SupportedResponse(str, Enum):
    """Define the possible response types that can be given feedback on."""
    CATCHY_TITLE_CREATOR = CatchyTitleCreatorResponse
    COVER_LETTER_WRITER = CoverLetterWriterResponse
    SANDBOX_CHATGPT = SandBoxChatGPTResponse
    TEXT_REVISOR = TextRevisorResponse
    TEXT_SUMMARIZER = TextSummarizerResponse


@docstring_parameter(ENDPOINT_NAME)
class FeedbackRequest(AIToolModel):
    """
    **Define the model for the request body for the {0} endpoint.**

    **Atrributes:**
    - user_prompt_feedback_context: The context of the user prompt that the feedback is for.
        Any of the AI tool request models can be used here. (templates or sandbox)
    - ai_response_feedback_context: The context of the AI response that the feedback is for.
        Any of the AI tool response models can be used here. (templates or sandbox)
    - star_rating: The star rating left by the user.
    - written_feedback: Any written feedback left by the user.
    """
    ai_tool_endpoint_name: AIToolsEndpointName
    user_prompt_feedback_context: SupportedRequest
    ai_response_feedback_context: SupportedResponse
    rating: Rating
    written_feedback: constr(min_length=0, max_length=500) = ""

    class Config:
        """Define the config for the model."""
        schema_extra = {
            "example": {
                "aiToolEndpointName": "templates",
                "userPromptFeedbackContext": {
                    "userPrompt": "Make me famous"
                },
                "aiResponseFeedbackContext": {
                    "aiResponse": "Famous"
                },
                "rating": 5,
                "writtenFeedback": "This was a great response"
            }
        }

@router.post(f"/{ENDPOINT_NAME}", status_code=status.HTTP_200_OK)
async def feedback(request: Request, response: Response, feedback_request: FeedbackRequest):
    """
    **POST User feedback for an AI tool.**

    This method is used to record user feedback for the AI tools. This method 
    returns an empty response with a 200 status code if the feedback is logged 
    successfully.
    """
    logger.info(f"Received request for {ENDPOINT_NAME} endpoint.")
    logger.info(f"Request body: {feedback_request.json()}")
    feedback_UUID = str(uuid4())
    feedback_table_model = FeedbackTableModel(
        feedback_UUID,
        ai_tool_name=feedback_request.ai_tool_endpoint_name.value,
        user_UUID=request.headers.get(UUID_HEADER_NAME),
        user_prompt_feedback_context=feedback_request.user_prompt_feedback_context.dict(),
        ai_response_feedback_context=feedback_request.ai_response_feedback_context.dict(),
        rating=feedback_request.rating.value,
    )
    if feedback_request.written_feedback:
        feedback_table_model.written_feedback = feedback_request.written_feedback
    feedback_table_model.save()
