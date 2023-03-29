"""Define the subscription router."""
from loguru import logger
import sys
from pathlib import Path
from fastapi import APIRouter, Request, Response, status
from email_validator import validate_email, EmailNotValidError
from pydantic import validator

router = APIRouter()

file_path = Path(__file__)
sys.path.append(str((file_path / "../dynamodb_models").resolve()))
sys.path.append(str((file_path.parent / "../utils").resolve()))
sys.path.append(str((file_path.parent).resolve()))
from utils import (
    AIToolModel,
    docstring_parameter,
    AIToolsEndpointName,
    UUID_HEADER_NAME,
)
from dynamodb_models import UserDataTableModel

ENDPOINT_NAME = "subscription"

@docstring_parameter(ENDPOINT_NAME)
class SubscriptionRequest(AIToolModel):
    """
    **Define the model for the request body for the {0} endpoint.**

    **Atrributes:**
    - email: The user email address to subscribe.
    """

    email_address: str

    class Config:
        """Define the config for the model."""
        schema_extra = {
            "example": {
                "email": "johndoe@gmail.com",
            }
        }

    @validator("email_address")
    def validate_email_address(cls, value):
        """Validate that the email address is valid."""
        try:
            validation = validate_email(value, check_deliverability=False)
            return validation.email
        except EmailNotValidError as error:
            raise ValueError(error)


@router.post(f"/{ENDPOINT_NAME}", status_code=status.HTTP_200_OK)
def subscription(request: Request, response: Response, subscription_request: SubscriptionRequest):
    """
    **POST User subscription for the app.**

    This method is used to record user subscriptions for the AI tools. This method 
    returns an empty response with a 200 status code if the subscription is logged 
    successfully.
    """
    uuid = request.headers.get(UUID_HEADER_NAME)
    logger.info(f"Received request from user {uuid} for {ENDPOINT_NAME} endpoint.")
    user_data_table_model = UserDataTableModel(
        hash_key=request.headers.get(UUID_HEADER_NAME),
        email_address=subscription_request.email_address,
        is_subscribed=True,
    )
    user_data_table_model.save()
    return {}