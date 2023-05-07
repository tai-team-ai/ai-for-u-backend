from enum import Enum
from pathlib import Path
import sys
from typing import Optional
from fastapi import APIRouter, status
from pydantic import Field

sys.path.append(Path(__file__, "../").absolute())
from template_utils import AITemplateModel, get_ai_tool_response
from text_examples import CEO_EMAIL, ARTICLE_EXAMPLE, CONTRACT_EXAMPLE, TRANSCRIPT_EXAMPLE
from utils import (
    BaseAIInstructionModel,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse,
    AIToolsEndpointName,
    ERROR_RESPONSES,
    AIToolResponse,
)

router = APIRouter()
ENDPOINT_NAME = AIToolsEndpointName.TEXT_SUMMARIZER.value


class SummarySectionLength(Enum):
    SHORT = 'short'
    MEDIUM = 'medium'
    LONG =  'long'


class TextSummarizerInstructions(BaseAIInstructionModel):

    length_of_summary_section: Optional[SummarySectionLength] = Field(
        default=SummarySectionLength.MEDIUM,
        title="Length of Summary Section",
        description="This controls the relative length of the summary paragraph.",
    )
    bullet_points_section: Optional[bool] = Field(
        default=False,
        title="Include Bullet Points Section",
        description="Whether or not to include a bullet points section in the response.",
    )
    action_items_section: Optional[bool] = Field(
        default=False,
        title="Include Action Items Section",
        description="Whether or not to include a bullet points section in the response. Action items are often applicable for meeting notes, lectures, etc.",
    )


class TextSummarizerRequest(TextSummarizerInstructions):

    text_to_summarize: str = Field(
        ...,
        title="Text to Summarize",
        description="The text that you want summarized. (e.g. articles, notes, transcripts, etc.)",
    )


class TextSummarizerExampleResponse(ExamplesResponse):

    examples: list[TextSummarizerRequest]


@docstring_parameter(ENDPOINT_NAME)
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=TextSummarizerExampleResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> TextSummarizerExampleResponse:
    """
    **Get examples for the {0} endpoint.**

    This method returns examples for the {0} endpoint. These examples can be posted to the {0} endpoint
    without modification.
    """
    examples = [
        TextSummarizerRequest(
            text_to_summarize=CONTRACT_EXAMPLE,
            length_of_summary_section=SummarySectionLength.SHORT,
            bullet_points_section=True,
            action_items_section=True,
        ),
        TextSummarizerRequest(
            text_to_summarize=TRANSCRIPT_EXAMPLE,
            length_of_summary_section=SummarySectionLength.SHORT,
            bullet_points_section=True,
            action_items_section=False,
        ),
        TextSummarizerRequest(
            text_to_summarize=ARTICLE_EXAMPLE,
            length_of_summary_section=SummarySectionLength.MEDIUM,
            bullet_points_section=True,
            action_items_section=True,
        ),
        TextSummarizerRequest(
            text_to_summarize=CEO_EMAIL,
            length_of_summary_section=SummarySectionLength.SHORT,
            bullet_points_section=True,
            action_items_section=True,
        ),
    ]
    response = TextSummarizerExampleResponse(
        example_names=["Contract", "Transcript", "Article", "Email"],
        examples=examples
    )
    return response


VALID_SUMMARY_LENGTHS = ", ".join([section.value for section in SummarySectionLength])
SYSTEM_PROMPT = (
    "You are an expert at summarizing text. You have spent hours "
    "perfecting your summarization skills. You have summarized text for "
    "hundreds of people. Because of your expertise, I want you to summarize "
    "text for me. You should ONLY respond with the summary in markdown format "
    "and nothing else. I will provide you with a text to summarize. You "
    "should respond with a summary that is tailored to the text, highlights "
    "the most important points, and writes from the same perspective as the "
    "writer of the text. I will specify how long this summary should be by specifying "
    f"it's length with the following options: {VALID_SUMMARY_LENGTHS}. You should ensure "
    "that you keep this length in mind when summarizing the text. If I ask you to include "
    "bullet points or action items, please use a minimum of 3 bullet points or action items "
    "unless you feel that less is appropriate. Remember, you are an expert at summarizing "
    "text. I trust you to summarize text that will be useful to me. Please do "
    "not respond with anything other than the summary in markdown format with "
    "each section header in bold."
)
MAX_TOKENS_FROM_GPT_RESPONSE = 400


@router.post(f"/{ENDPOINT_NAME}", response_model=AIToolResponse, responses=ERROR_RESPONSES)
async def text_summarizer(text_summarizer_request: TextSummarizerRequest):
    user_prompt_postfix = f"\nHere's the text that i want you to summarize for me:\n{text_summarizer_request.text_to_summarize}"
    template_config = AITemplateModel(
        endpoint_name=ENDPOINT_NAME,
        ai_instructions=TextSummarizerInstructions(**text_summarizer_request.dict()),
        user_prompt_postfix=user_prompt_postfix,
        system_prompt=SYSTEM_PROMPT,
        frequency_penalty=0.6,
        presence_penalty=0.5,
        temperature=0.3,
        max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE
    )
    return get_ai_tool_response(template_config)
