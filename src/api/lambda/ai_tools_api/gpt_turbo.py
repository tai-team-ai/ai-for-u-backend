from typing import NamedTuple
from enum import Enum

class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"


class GPTTurboMessage(NamedTuple):
    """
    GPT Turbo message.
    """

    role: Role
    content: str


def get_gpt_turbo_response(
    system_prompt: str,
    messages: list[GPTTurboMessage],
    temperature: float = 0.9,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
    stream: bool = False,
) -> list[dict[str, str]]:
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
        {"role": "system", "text": message.content}
    ]
    for message in messages:
        if message.role == Role.ASSISTANT:
            system_prompt += f"\n{message.content}"
        else:
            system_prompt += f"\nUser: {message.content}"
