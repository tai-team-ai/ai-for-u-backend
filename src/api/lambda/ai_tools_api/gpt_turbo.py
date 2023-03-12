from __future__ import annotations
from pydantic import BaseModel
from enum import Enum
import openai
from uuid import UUID


class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"


class GPTTurboMessage(BaseModel):
    """
    GPT Turbo message.
    """

    role: Role
    content: str


class GPTTurboMessageHistory(BaseModel):
    """
    GPT Turbo message history.
    """

    message_uuid: UUID
    messages: tuple[GPTTurboMessage, ...]

    class Config:
        """Set configuration for GPT Turbo message history model"""

        schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hello, how can I help?"},
                ]
            }
        }
        allow_mutation = False

    def add_message(self, message: GPTTurboMessage) -> GPTTurboMessageHistory:
        """Add message to message history and return new message history model"""
        new_messages = self.messages + (message,)
        return GPTTurboMessageHistory(message_uuid=self.message_uuid, messages=new_messages)


def get_gpt_turbo_response(
    system_prompt: str,
    messages: list[GPTTurboMessage],
    temperature: float = 0.9,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    stream: bool = False,
    uuid: str = None,
) -> list[GPTTurboMessage]:
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
        {"role": "system", "text": system_prompt}
    ]
    for message in messages:
        prompt_messages.append({"role": message.role.value, "text": message.content})

    response = openai.Completion.create(
        model="gpt-3.5-turbo",
        messages=prompt_messages,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        stream=stream,
        user=uuid
    )

    message = response.choices[0].message.content
    messages.append(GPTTurboMessage(Role.ASSISTANT, message))
    return messages
