from __future__ import annotations
from pydantic import BaseModel
from enum import Enum
import openai
from utils import does_user_have_enough_tokens_to_make_request


class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"


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
        {"role": "system", "content": system_prompt}
    ]
    chat_history_cumulative_token_count = 0
    for chat in chat_session.messages:
        chat_history_cumulative_token_count += chat.token_count
        prompt_messages.append(chat.dict(exclude={"token_count"}))
    tokens_for_request = chat_history_cumulative_token_count + max_tokens
    can_user_make_request, tokens_allowed = does_user_have_enough_tokens_to_make_request(
        user_uuid=uuid,
        expected_token_count=tokens_for_request,
    )
    if not can_user_make_request:
        raise Exception(f"User does not have enough tokens to make request. Token quota: {tokens_allowed}, Tokens required for request: {tokens_for_request}")

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=prompt_messages,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        stream=stream,
        user=uuid,
        max_tokens=max_tokens,
    )

    message = response.choices[0].message.content
    token_count = response.usage.total_tokens
    chat_session = chat_session.add_message(GPTTurboChat(
        role=Role.ASSISTANT,
        content=message,
        token_count=token_count
    ))
    return chat_session
