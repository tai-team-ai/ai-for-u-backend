from typing import Union
from loguru import logger
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from gpt_turbo import GPTTurboChat, Role, GPTTurboChatSession, get_gpt_turbo_response
from utils import (
    TOKENS_EXHAUSTED_FOR_DAY_JSON_RESPONSE,
    TOKENS_EXHAUSTED_LOGIN_JSON_RESPONSE,
    BaseAIInstructionModel,
    TokensExhaustedException,
    append_field_prompts_to_prompt,
    BASE_USER_PROMPT_PREFIX,
    AIToolResponse,
    sanitize_string,
)

class AITemplateModel(BaseModel):
    endpoint_name: str
    ai_instructions: BaseAIInstructionModel
    user_prompt_prefix: str = ""
    user_prompt_postfix: str = ""
    system_prompt: str = ""
    frequency_penalty: float = 0.4
    presence_penalty: float = 0.6
    temperature: float = 0.4
    max_tokens: int = 400


def prepare_template_chat(
    endpoint_name: str,
    template_instructions: BaseAIInstructionModel,
    template_prefix_prompt: str = "",
    template_postfix_prompt: str = "",
) -> GPTTurboChat:
    logger.info(f"Received request for {endpoint_name} endpoint.")
    user_prompt = template_prefix_prompt
    user_prompt += append_field_prompts_to_prompt(template_instructions, BASE_USER_PROMPT_PREFIX)
    user_prompt += template_postfix_prompt
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=user_prompt,
    )
    return user_chat

def handle_token_exhausted_error(error: TokensExhaustedException) -> JSONResponse:
    if error.login:
        return TOKENS_EXHAUSTED_LOGIN_JSON_RESPONSE
    return TOKENS_EXHAUSTED_FOR_DAY_JSON_RESPONSE

def get_ai_tool_response_model(endpoint_name: str, chat_session: GPTTurboChatSession) -> AIToolResponse:
    latest_gpt_chat_model = chat_session.messages[-1]
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)
    response_model = AIToolResponse(
        response=latest_chat
    )
    logger.info(f"Returning response for {endpoint_name} endpoint.")
    return response_model


def get_ai_tool_response(config: AITemplateModel) -> Union[JSONResponse, AIToolResponse]:
    user_chat = prepare_template_chat(
        config.endpoint_name,
        config.ai_instructions,
        config.user_prompt_prefix,
        config.user_prompt_postfix,
    )
    try:
        chat_session = get_gpt_turbo_response(
            system_prompt=config.system_prompt,
            chat_session=GPTTurboChatSession(messages=[user_chat]),
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
    except TokensExhaustedException as e:
        return handle_token_exhausted_error(e)

    return get_ai_tool_response_model(config.endpoint_name, chat_session)
