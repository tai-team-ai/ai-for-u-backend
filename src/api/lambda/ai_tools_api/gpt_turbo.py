from __future__ import annotations
from pydantic import BaseModel
from enum import Enum
import openai


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


class GPTTurboChatSession(BaseModel):
    """
    GPT Turbo message history.
    """

    messages: tuple[GPTTurboChat, ...]

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
    uuid: str = None,
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
    for message in chat_session.messages:
        prompt_messages.append({"role": message.role.value, "content": message.content})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=prompt_messages,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        stream=stream,
        user=uuid
    )

    message = response.choices[0].message.content
    chat_session = chat_session.add_message(GPTTurboChat(role=Role.ASSISTANT, content=message))
    return chat_session
