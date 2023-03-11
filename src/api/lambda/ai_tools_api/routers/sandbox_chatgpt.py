from pathlib import Path
import sys
from typing import Optional
from fastapi import APIRouter, status

from pydantic import constr


sys.path.append(Path(__file__, "../utils").absolute())
from utils import CamelCaseModel

router = APIRouter()

class SandBoxChatGPTRequest(CamelCaseModel):
    conversation_id: constr(regex=r"^[a-zA-Z0-9]{5}$")
    prompt: Optional[str] = ""


class SandBoxChatGPTResponse(CamelCaseModel):
    gpt_response: str


class SandBoxChatGPTExamples(CamelCaseModel):
    example_names: list[str]
    examples: list[str]


@router.get("/sandbox-chatgpt-examples", response_model=SandBoxChatGPTExamples, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> SandBoxChatGPTExamples:
    """
    Get examples for sandbox-chatgpt.

    Returns:
        examples: Examples for sandbox-chatgpt.
    """
    return SandBoxChatGPTExamples(example_names=[], examples=[])


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
