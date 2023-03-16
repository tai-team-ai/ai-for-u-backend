from pathlib import Path
import sys
import logging
import traceback
from typing import Optional, Generator, Union
from uuid import UUID
from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse
from typing import Any, Dict
from pynamodb.models import Model
from pynamodb.pagination import ResultIterator



sys.path.append(Path(__file__, "../utils").absolute())
sys.path.append(Path(__file__, "../gpt_turbo").absolute())
sys.path.append(Path(__file__, "../dynamodb_models").absolute())
from utils import CamelCaseModel, UUID_HEADER_NAME, sanitize_string
from gpt_turbo import GPTTurboChatSession, get_gpt_turbo_response, GPTTurboChat, Role
from dynamodb_models import UserDataTableModel

router = APIRouter()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_TOKENS = 400

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
    * Request 1: {"conversation_id": "id", "prompt": ""}\n\n
    * Response 1: {"gpt_response": "Hi, how are you?"}\n\n
    * Request 2: {"conversation_id": "id", "prompt": "I'm good, how are you?"}\n\n
    * Response 2: {"gpt_response": "I'm good, thanks for asking."}\n\n

    ### Attributes:
        conversation_uuid: A unique identifier for the conversation (generated by the client)
        user_message: The prompt to send to the model. The prompt should only include the user's response to the model's prompt.
    """

    conversation_uuid: UUID
    user_message: Optional[str] = ""
    stream_messages: Optional[bool] = False


class SandBoxChatGPTResponse(CamelCaseModel):
    gpt_response: str
    
    
class GPTChatHistory(GPTTurboChatSession):
    conversation_uuid: UUID


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
    examples: list[SandBoxChatGPTRequest]


@router.get("/sandbox-chatgpt-examples", response_model=SandBoxChatGPTExamplesResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> SandBoxChatGPTExamplesResponse:
    """
    Get examples for sandbox-chatgpt.

    Returns:
        examples: Examples for sandbox-chatgpt.
    """
    response = SandBoxChatGPTExamplesResponse(
        example_names=["How to Cook Ramen"],
        examples=["I want to cook ramen. What ingredients do I need?"]
    )
    return response


def load_sandbox_chat_history(user_uuid: UUID, conversation_uuid: UUID) -> GPTChatHistory:
    """
    Load the chat history for a sandbox-chatgpt session.

    Args:
        conversation_uuid: A unique identifier for the conversation (generated by the client)

    Returns:
        chat_history: Chat history for a sandbox-chatgpt session.
    """
    try:
        results: ResultIterator[UserDataTableModel] = UserDataTableModel.query(str(user_uuid))
        chat_history: Dict[str, Any] = next(results).sandbox_chat_history
        if chat_history:
            chat_history = GPTChatHistory(**chat_history)
            if chat_history.conversation_uuid == conversation_uuid:
                return chat_history
    except (Model.DoesNotExist, StopIteration, KeyError):
        logger.error(traceback.format_exc())
    return GPTChatHistory(conversation_uuid=conversation_uuid)

def save_sandbox_chat_history(user_uuid: UUID, sandbox_chat_history: GPTChatHistory) -> None:
    """
    Save the chat history for a sandbox-chatgpt session.

    Args:
        chat_session: Chat history for a sandbox-chatgpt session.
    """
    token_count = sandbox_chat_history.messages[-1].token_count
    chat_dict = sandbox_chat_history.dict()
    chat_dict["conversation_uuid"] = str(sandbox_chat_history.conversation_uuid)
    try:
        results: ResultIterator[UserDataTableModel] = UserDataTableModel.query(str(user_uuid))
        user_data_table_model = next(results)
        new_token_count = token_count + user_data_table_model.cumulative_token_count
        new_user_model = UserDataTableModel(str(user_uuid), new_token_count, sandbox_chat_history=chat_dict)
        user_data_table_model.delete()
    except (Model.DoesNotExist, StopIteration):
        new_user_model = UserDataTableModel(str(user_uuid), token_count, sandbox_chat_history=chat_dict)
    new_user_model.save()


def event_stream(chat_session: GPTTurboChatSession) -> Generator[str, None, None]:
    """
    Stream response from GPT Turbo to client.

    Args:
        chat_session: GPTTurboChatSession object.

    Returns:
        response: Generator object that streams the response.
    """
    for message in chat_session.messages[len(chat_session.messages)-1:]:
        yield f"data: {message.content}\n\n"


@router.post("/sandbox-chatgpt", response_model=SandBoxChatGPTResponse, status_code=status.HTTP_200_OK)
def sandbox_chatgpt(sandbox_chatgpt_request: SandBoxChatGPTRequest, request: Request) -> SandBoxChatGPTResponse:
    """
    Get response from openAI Turbo GPT-3 model.

    Args:
        sandbox_chatgpt_request: Request containing conversation_id and prompt.

    Returns:
        gpt_response: Response from openAI Turbo GPT-3 model.
    """
    uuid = request.headers.get(UUID_HEADER_NAME)
    logger.info("User Request: %s", sandbox_chatgpt_request)
    chat_history = load_sandbox_chat_history(user_uuid=uuid, conversation_uuid=sandbox_chatgpt_request.conversation_uuid)
    chat_history = chat_history.add_message(GPTTurboChat(role=Role.USER, content=sandbox_chatgpt_request.user_message))
    chat_session = get_gpt_turbo_response(
        system_prompt=SYSTEM_PROMPT,
        chat_session=GPTTurboChatSession(**chat_history.dict()),
        frequency_penalty=0.9,
        temperature=0.9,
        uuid=uuid,
        max_tokens=MAX_TOKENS,
        stream=sandbox_chatgpt_request.stream_messages
    )
    logger.info("chat_session after response: %s", chat_session)
    chat_history = GPTChatHistory(**chat_session.dict(), conversation_uuid=sandbox_chatgpt_request.conversation_uuid)
    save_sandbox_chat_history(user_uuid=uuid, sandbox_chat_history=chat_history)

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_message = latest_gpt_chat_model.content
    latest_message = sanitize_string(latest_message)
    response = SandBoxChatGPTResponse(gpt_response=latest_message)
    logger.info("Response: %s", response)
    return response


@router.post("/sandbox-chatgpt", response_model=Union[SandBoxChatGPTResponse, StreamingResponse], status_code=status.HTTP_200_OK)
def sandbox_chatgpt(sandbox_chatgpt_request: SandBoxChatGPTRequest, request: Request) -> Union[SandBoxChatGPTResponse, StreamingResponse]:
    """
    Get response from openAI Turbo GPT-3 model.

    Args:
        sandbox_chatgpt_request: Request containing conversation_id and prompt.

    Returns:
        gpt_response: Response from openAI Turbo GPT-3 model.
    """
    chat_session = GPTTurboChatSession()

    # Get system prompt
    system_prompt = "Hello, how may I assist you today?"
    chat_session = get_gpt_turbo_response(system_prompt, chat_session, stream=False)

    # Add user message to chat session
    chat_session = chat_session.add_message(GPTTurboChat(
        role=Role.USER,
        content=sandbox_chatgpt_request.user_message
    ))

    # Stream messages
    if sandbox_chatgpt_request.stream_messages:
        return StreamingResponse(
            event_stream(chat_session),
            media_type="text/event-stream",
        )

    # Get GPT Turbo response
    chat_session = get_gpt_turbo_response(system_prompt, chat_session, stream=False)

    # Log response to database
    <database call>

    # Return response
    return SandBoxChatGPTResponse(gpt_response=chat_session.messages[-1].content)