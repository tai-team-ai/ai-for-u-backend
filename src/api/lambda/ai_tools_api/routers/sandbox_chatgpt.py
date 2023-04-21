from pathlib import Path
import sys
import logging
import traceback
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Request, status
from typing import Any, Dict
from pynamodb.models import Model

sys.path.append(Path(__file__, "../utils"))
sys.path.append(Path(__file__, "../gpt_turbo"))
sys.path.append(Path(__file__, "../dynamodb_models"))
from utils import (
    AIToolModel,
    UUID_HEADER_NAME,
    EXAMPLES_ENDPOINT_POSTFIX,
    AIToolsEndpointName,
    error_responses,
    TokensExhaustedException,
    TOKEN_EXHAUSTED_JSON_RESPONSE,
)
from gpt_turbo import GPTTurboChatSession, get_gpt_turbo_response, GPTTurboChat, Role
from dynamodb_models import UserDataTableModel

logger = logging.getLogger()
logger.setLevel(logging.INFO)

router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.SANDBOX_CHATGPT.value

SYSTEM_PROMPT = (
    "You are a friendly assist named Roo. You are to act as someone who is friendly and "
    "helpful. You are to help the user with whatever they need help with but also be conversational. "
    "You are to be a good listener and ask how you can help and be there for them. You work for a "
    "site that is called AI for U which seeks to empower EVERYONE to feel comfortable using AI. "
    "Most IMPORTANTLY, you need to ask questions to understand the user as best as possible. "
    "This will allow you to better understand who the person is and what they need help with. "
    "You should also ask questions to make sure you understand what the user is saying. "
    "You MUST get to know them as a human being and understand their needs in order to be successful."
    "Finally, you MUST use markdown format when you respond to the user."
)


class SandBoxChatGPTRequest(AIToolModel):
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


class SandBoxChatGPTResponse(AIToolModel):
    gpt_response: str
    
    
class GPTChatHistory(GPTTurboChatSession):
    conversation_uuid: UUID


class SandBoxChatGPTExamplesResponse(AIToolModel):
    """
    **Define example starter prompts for sandbox-chatgpt endpoint.**

    **Example:**
    * example_names: ["How to Cook Ramen"] \n\n
    * examples: ["I want to cook ramen. What ingredients do I need?"]

    **Attributes:**
    **example_names:** List of example names. \n\n
    **examples:** List of corresponding example prompts.
    """
    example_names: list[str]
    examples: list[str]


@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=SandBoxChatGPTExamplesResponse, responses=error_responses)
async def sandbox_chatgpt_examples() -> SandBoxChatGPTExamplesResponse:
    """
    Get examples for sandbox-chatgpt.

    Returns:
        examples: Examples for sandbox-chatgpt.
    """
    return SandBoxChatGPTExamplesResponse(
        example_names=["How to Cook Ramen"],
        examples=["I want to cook ramen. What ingredients do I need?"]
    )


def load_sandbox_chat_history(user_uuid: UUID, conversation_uuid: UUID) -> GPTChatHistory:
    """
    Load the chat history for a sandbox-chatgpt session.

    Args:
        conversation_uuid: A unique identifier for the conversation (generated by the client)

    Returns:
        chat_history: Chat history for a sandbox-chatgpt session.
    """
    try:
        user_data_table_model = UserDataTableModel.get(str(user_uuid))
        chat_history: Dict[str, Any] = user_data_table_model.sandbox_chat_history
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
    token_count += sandbox_chat_history.messages[-2].token_count # add token count for system prompt
    chat_dict = sandbox_chat_history.dict()
    chat_dict["conversation_uuid"] = str(sandbox_chat_history.conversation_uuid)
    try:
        user_data_model: UserDataTableModel = UserDataTableModel.get(str(user_uuid))
    except (Model.DoesNotExist, StopIteration):
        user_data_model = UserDataTableModel(str(user_uuid), sandbox_chat_history=chat_dict)
    user_data_model.cumulative_token_count + token_count


@router.post(f"/{ENDPOINT_NAME}", response_model=SandBoxChatGPTResponse, responses=error_responses)
def sandbox_chatgpt(sandbox_chatgpt_request: SandBoxChatGPTRequest, request: Request) -> SandBoxChatGPTResponse:
    """
    Get response from openAI Turbo GPT-3 model.

    Args:
        sandbox_chatgpt_request: Request containing conversation_id and prompt.

    Returns:
        gpt_response: Response from openAI Turbo GPT-3 model.
    """
    uuid = request.headers.get(UUID_HEADER_NAME)
    logger.info("uuid: %s", uuid)
    chat_session = load_sandbox_chat_history(user_uuid=uuid, conversation_uuid=sandbox_chatgpt_request.conversation_uuid)
    logger.info("chat_session before response: %s", chat_session)
    chat_session = chat_session.add_message(GPTTurboChat(role=Role.USER, content=sandbox_chatgpt_request.user_message))
    try:
        chat_session = get_gpt_turbo_response(
            system_prompt=SYSTEM_PROMPT,
            chat_session=chat_session,
            frequency_penalty=0.9,
            temperature=0.9,
            uuid=uuid,
            max_tokens=400
        )
    except TokensExhaustedException:
        return TOKEN_EXHAUSTED_JSON_RESPONSE
    logger.info("chat_session after response: %s", chat_session)
    chat_history = GPTChatHistory(**chat_session.dict(), conversation_uuid=sandbox_chatgpt_request.conversation_uuid)
    save_sandbox_chat_history(user_uuid=uuid, sandbox_chat_history=chat_history)

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_message = latest_gpt_chat_model.content
    return SandBoxChatGPTResponse(gpt_response=latest_message)







# async def get_gpt_turbo_response_stream(
#     system_prompt: str,
#     chat_session: GPTTurboChatSession,
#     temperature: float = 0.9,
#     frequency_penalty: float = 0.0,
#     presence_penalty: float = 0.0,
#     stream: bool = False,
#     uuid: str = "",
#     max_tokens: int = 400,
# ):
#     # ... (same code as before, up to the response creation)

#     response = openai.ChatCompletion.create(
#         model=GPT_MODEL,
#         messages=prompt_messages,
#         temperature=temperature,
#         frequency_penalty=frequency_penalty,
#         presence_penalty=presence_penalty,
#         stream=stream,
#         user=uuid,
#         max_tokens=max_tokens,
#     )

#     async for message in response.iter_chunks():
#         yield message
# ```

# 3. Update the WebSocket route to forward the events to the user:

# ```python
# @app.websocket("/ws/{conversation_id}")
# async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
#     await websocket.accept()

#     while True:
#         user_message = await websocket.receive_text()
#         uuid = websocket.headers.get(UUID_HEADER_NAME)

#         chat_session = load_sandbox_chat_history(user_uuid=uuid, conversation_uuid=conversation_id)
#         chat_session = chat_session.add_message(GPTTurboChat(role=Role.USER, content=user_message))

#         try:
#             response_stream = get_gpt_turbo_response_stream(
#                 system_prompt=SYSTEM_PROMPT,
#                 chat_session=chat_session,
#                 frequency_penalty=0.9,
#                 temperature=0.9,
#                 uuid=uuid,
#                 max_tokens=400
#             )
            
#             async for message in response_stream:
#                 await websocket.send_text(message)

#         except TokensExhaustedException:
#             await websocket.send_text(TOKEN_EXHAUSTED_JSON_RESPONSE)
#             continue