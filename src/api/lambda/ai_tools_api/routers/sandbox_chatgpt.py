from pathlib import Path
import sys
from typing import Optional
from fastapi import APIRouter, status

from pydantic import constr


sys.path.append(Path(__file__, "../utils").absolute())
from utils import CamelCaseModel

router = APIRouter()


SYSTEM_PROMPT = (
    "You are a friendly assist named Roo. You are to act as someone who is friendly and "
    "helpful. You are to help the user with whatever they need help with but also be conversational. "
    "You are to be a good listener and ask how you can help and be there for them. You work for a "
    "site that is called AI for U which seeks to empower EVERYONE to feel comfortable using AI. "
    "You should assume the user is not technical unless they ask you a technical question.\n"
    "Most IMPORTANTLY, you need to ask questions to understand the user as best as possible. "
    "This will allow you to better understand who the person is and what they need help with. "
    "You should also ask questions to make sure you understand what the user is saying. "
    "You MUST get to know them as a human being and understand their needs in order to be successful."
)


class SandBoxChatGPTRequest(CamelCaseModel):
    """
    ## Define the request body for sandbox-chatgpt endpoint.

    When a conversation is started, the client should send a request with a conversation_id and an empty prompt.
    The response will contain the initial prompt from the model. The client should then send a request with the 
    conversation_id for each subsequent prompt. The prompt should only include the user's response to the model's 
    prompt.

    ### Example Conversation:
    * Request 1: {"conversation_id": "12345", "prompt": ""}\n\n
    * Response 1: {"gpt_response": "Hi, how are you?"}\n\n
    * Request 2: {"conversation_id": "12345", "prompt": "I'm good, how are you?"}\n\n
    * Response 2: {"gpt_response": "I'm good, thanks for asking."}\n\n

    ### Attributes:
        conversation_id: A unique identifier for the conversation\n\n
        prompt: The prompt to send to the model. The prompt should only include the user's response to the model's prompt.
    """

    conversation_id: constr(regex=r"^[a-zA-Z0-9]{5}$")
    prompt: Optional[str] = ""


class SandBoxChatGPTResponse(CamelCaseModel):
    gpt_response: str


class SandBoxChatGPTExamplesResponse(CamelCaseModel):
    """
    ## Define example starter prompts for sandbox-chatgpt endpoint.

    ### Example:
    * example_names: ["How to Cook Ramen"] \n\n
    * examples: ["I want to cook ramen. What ingredients do I need?"]

    ### Attributes:
        example_names: List of example names. \n\n
        examples: List of corresponding example prompts.
    """
    example_names: list[str]
    examples: list[str]


@router.get("/sandbox-chatgpt-examples", response_model=SandBoxChatGPTExamplesResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> SandBoxChatGPTExamplesResponse:
    """
    Get examples for sandbox-chatgpt.

    Returns:
        examples: Examples for sandbox-chatgpt.
    """
    return SandBoxChatGPTExamplesResponse(example_names=[], examples=[])


@router.post("/sandbox-chatgpt", response_model=SandBoxChatGPTResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt(sandbox_chatgpt_request: SandBoxChatGPTRequest) -> SandBoxChatGPTResponse:
    """
    Get response from openAI Turbo GPT-3 model.

    Args:
        sandbox_chatgpt_request: Request containing conversation_id and prompt.

    Returns:
        gpt_response: Response from openAI Turbo GPT-3 model.
    """
    return SandBoxChatGPTResponse(gpt_response="")
