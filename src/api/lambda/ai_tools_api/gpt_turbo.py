from __future__ import annotations
from typing import Generator
from enum import Enum
from pydantic import BaseModel
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
    
    def add_message(self, chat: GPTTurboChat) -> GPTTurboChatSession:
        """Add a message to the chat session and return a new chat session model"""
        new_messages = self.messages + (chat,)
        return GPTTurboChatSession(messages=new_messages)
    
    def merge_last_message_and_tokens_if_same_role(self, chat: GPTTurboChat) -> GPTTurboChatSession:
        """Merge the last message and tokens if the last message has the same role as the chat message"""
        if self.messages[-1].role == chat.role:
            new_messages = self.messages[:-1] + (GPTTurboChat(
                role=chat.role,
                content=self.messages[-1].content + chat.content,
                token_count=self.messages[-1].token_count + chat.token_count,
            ),)
            return GPTTurboChatSession(messages=new_messages)
        else:
            return self.add_message(chat)


def count_tokens(messages: str) -> int:
    return len(messages.split())

class GeneratorWrapper:
    def __init__(self, generator):
        self.generator = generator
        self.value = None
    
    def __iter__(self):
        self.value = yield from self.generator
        
    def __next__(self):
        return next(self.generator)


def get_gpt_turbo_response(
    system_prompt: str,
    chat_session: GPTTurboChatSession,
    temperature: float = 0.9,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    stream: bool = False,
    uuid: str = "",
    max_tokens: int = 400,
) -> Generator[GPTTurboChatSession, None, GPTTurboChatSession]:
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

    for chat in chat_session.messages:
        prompt_messages.append(chat.dict(exclude={"token_count"}))

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
    if stream:
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta == {}:
                return chat_session
            message = chunk.choices[0].delta.get("content", None)
            if message:
                token_count = count_tokens(message)
                chat_session = chat_session.merge_last_message_and_tokens_if_same_role(
                    GPTTurboChat(
                        role=Role.ASSISTANT,
                        content=message,
                        token_count=token_count,
                    )
                )
                yield chat_session
    else:
        message = response.choices[0].message.content
        token_count = response.usage.total_tokens
        chat_session = chat_session.add_message(GPTTurboChat(
            role=Role.ASSISTANT,
            content=message,
            token_count=token_count
        ))
        return chat_session
