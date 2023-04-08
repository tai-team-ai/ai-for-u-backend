from __future__ import annotations
from pydantic import BaseModel
from enum import Enum
import openai
import tiktoken
from loguru import logger
from utils import does_user_have_enough_tokens_to_make_request, docstring_parameter, TokensExhaustedException


MODEL_CONTEXT_WINDOW = 4096
GPT_MODEL = "gpt-3.5-turbo"
MODEL_ENCODING = tiktoken.encoding_for_model(GPT_MODEL)


class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class GPTTurboChat(BaseModel):
    """
    GPT Turbo chat message.

    Attributes:
        role: The role of the message.
        content: The content of the message.
    """

    role: Role
    content: str
    token_count: int = 0

    class Config:
        use_enum_values = True


class GPTTurboChatSession(BaseModel):
    """
    GPT Turbo message history.
    """

    messages: tuple[GPTTurboChat, ...] = ()

    class Config:
        """Config for GPT Turbo message history."""

        schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hello, how can I help?"},
                ]
            }
        }
        allow_mutation = False
    
    def add_message(self, message: GPTTurboChat) -> GPTTurboChatSession:
        """Add a message to the chat session and return a new chat session model"""
        new_messages = self.messages + (message,)
        return GPTTurboChatSession(messages=new_messages)

def can_user_make_request(user_uuid: str, expected_token_count: int) -> None:
    """
    Check if a user has enough tokens to make a request.

    Args:
        user_uuid: The user's UUID.
        expected_token_count: The expected token count of the request.

    Returns:
        can_user_make_request: Whether the user can make the request.
        tokens_allowed: The number of tokens the user is allowed to use.
    """
    can_make_request, tokens_allowed = does_user_have_enough_tokens_to_make_request(
        user_uuid=user_uuid,
        expected_token_count=expected_token_count,
    )
    if not can_make_request:
        raise TokensExhaustedException(f"User does not have enough tokens to make request. Token quota: {tokens_allowed}, Tokens required for request: {expected_token_count}")


def count_tokens(string: str) -> int:
    """
    Get the token count of a string.

    Args:
        string: The string to get the token count of.

    Returns:
        token_count: The token count of the string.
    """
    return len(MODEL_ENCODING.encode(string))


@docstring_parameter(MODEL_CONTEXT_WINDOW)
def truncate_chat_session(chat_session: GPTTurboChatSession, overhead_tokens: int) -> GPTTurboChatSession:
    """
    Truncate the chat session to the model context window ({0})

    This function truncates the chat session to the model context window. This is 
    necessary because the model can only handle a certain number of tokens in the 
    context window. This truncation is done by removing the oldest messages until
    the tokens from the session and the tokens from the request are less than the
    model context window.

    Args:
        chat_session: The chat session to truncate.
        overhead_tokens: The number of tokens to add to account for system and response tokens.
    
    Returns:
        chat_session: The truncated chat session.
    """
    chat_history_cumulative_token_count = 0
    for chat in chat_session.messages:
        chat_history_cumulative_token_count += chat.token_count
    while chat_history_cumulative_token_count + overhead_tokens > MODEL_CONTEXT_WINDOW:
        chat_history_cumulative_token_count -= chat_session.messages[0].token_count
        chat_session = GPTTurboChatSession(messages=chat_session.messages[1:])
        logger.info(chat_session)
    return chat_session


def get_gpt_turbo_response(
    system_prompt: str,
    chat_session: GPTTurboChatSession,
    temperature: float = 0.9,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    stream: bool = False,
    uuid: str = "",
    max_tokens: int = 400,
) -> GPTTurboChatSession:
    """
    Get response from GPT Turbo.

    Args:
        system_prompt: The system prompt to send to the model.
        messages: The messages to send to the model.
        temperature: The temperature of the model. Higher values will result in more creative responses, lower values will result in more conservative responses.
        frequency_penalty: The frequency penalty of the model. This is a value between 0 and 1 that penalizes new tokens based on whether they appear in the text so far. Higher values will result in more creative responses, lower values will result in more conservative responses.
        presence_penalty: The presence penalty of the model. This is a value between 0 and 1 that penalizes new tokens based on whether they appear in the text so far. Higher values will result in more creative responses, lower values will result in more conservative responses.
        stream: Whether to stream the response.

    Returns:
        response: Response from GPT Turbo.
    """
    prompt_messages = [
        {"role": Role.SYSTEM.value, "content": system_prompt}
    ]

    system_token_count = count_tokens(system_prompt)
    tokens_for_request = system_token_count + max_tokens
    # This line counts the tokens for the last user message and adds it to the chat session
    chat_session.messages[-1].token_count = count_tokens(chat_session.messages[-1].content)
    chat_session = truncate_chat_session(chat_session, tokens_for_request)
    for chat in chat_session.messages:
        tokens_for_request += chat.token_count
        prompt_messages.append(chat.dict(exclude={"token_count"}))
    can_user_make_request(uuid, tokens_for_request)
    logger.info(f"Prompt messages: {prompt_messages}")

    response = openai.ChatCompletion.create(
        model=GPT_MODEL,
        messages=prompt_messages,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        stream=stream,
        user=uuid,
        max_tokens=max_tokens,
    )

    message = response.choices[0].message.content
    completion_tokens = response.usage.completion_tokens
    chat_session = chat_session.add_message(GPTTurboChat(
        role=Role.ASSISTANT,
        content=message,
        token_count=completion_tokens,
    ))
    return chat_session
