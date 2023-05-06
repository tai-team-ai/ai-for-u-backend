import logging
import sys
import os
from typing import Optional, List
from pathlib import Path
from pydantic import constr, Field
from fastapi import APIRouter, Request, Response, status

from template_utils import AITemplateModel, get_ai_tool_response
sys.path.append(Path(__file__).parent / "../utils")
sys.path.append(Path(__file__).parent / "../text_examples")
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../gpt_turbo"))
from text_examples import AEROSPACE_RESUME, SPACEX_JOB_POSTING, TEACHER_JOB_POSTING, TEACHER_RESUME
from utils import (
    BaseAIInstructionModel,
    Tone,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse,
    AIToolsEndpointName,
    error_responses,
    AIToolResponse,
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.COVER_LETTER_WRITER.value
MAX_TOKENS_FROM_GPT_RESPONSE = 400

class CoverLetterWriterInstructions(BaseAIInstructionModel):
    job_posting: constr(min_length=1, max_length=10000) = Field(
        ...,
        title="Job Posting",
        description="The job posting to generate a cover letter for.",
    )
    company_name: Optional[constr(min_length=1, max_length=50)] = Field(
        title="Company Name",
        description="The name of the company you are applying to.",
    )
    skills_to_highlight_from_resume: constr(min_length=1, max_length=1000) = Field(
        ...,
        title="Skills to Highlight from Resume",
        description="What are your strengths? What skills do you have that are most relevant to the job posting?",
    )
    tone: Optional[Tone] = Field(
        default=Tone.ASSERTIVE,
        title="Tone of the Cover Letter",
        description="The tone used when writing the cover letter.",
    )

SYSTEM_PROMPT = (
    "You are an expert at writing cover letters. You have spent hours "
    "perfecting your cover letter writing skills. You have written cover "
    "letters for hundreds of people. Because of your expertise, I want you "
    "to write a cover letter for me. You should ONLY respond with the "
    "cover letter and nothing else. I will provide you with a resume, job "
    "posting, and optionally a company name to write a cover letter for. You "
    "should respond with a cover letter that is tailored to the job posting "
    "and company, highlights my skills, and demonstrates enthusiasm for "
    "the company and role. I may also ask you to specifically highlight "
    "certain skills from my resume that i feel are most relevant to the job "
    "posting. It is important that you highlight these skills if I ask you to. "
    "Remember, you are an expert at writing cover letters. I trust you to "
    "write a cover letter that will get me the job. Please do not respond with "
    "anything other than the cover letter."
)


class CoverLetterWriterRequest(CoverLetterWriterInstructions):
    """
    **Define the model for the request body for {0} endpoint.**
    
    **Atrributes:**
    - resume: The resume to generate a cover letter for.
    - job_posting: The job posting to generate a cover letter for.
    - skills_to_highlight_from_resume: The skills to highlight from the resume.

    **AI Instructions:**

    """
    
    resume: constr(min_length=1, max_length=10000) = Field(
        ...,
        title="Resume",
        description="Your resume. Don't worry too much if the formatting isn't perfect.",
    )



class CoverLetterWriterExamplesResponse(ExamplesResponse):
    """
    **Define the model for the response body for {0} examples endpoint.**
    
    Inherits from ExamplesResponse:
    """

    __doc__ += ExamplesResponse.__doc__
    examples: list[CoverLetterWriterRequest]


@docstring_parameter(ENDPOINT_NAME)
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=CoverLetterWriterExamplesResponse)
async def cover_letter_writer_examples(request: Request):
    """
    **Get examples for the {0} endpoint.**
    
    This method returns a list of examples for the {0} endpoint. These examples can be posted to the {0} endpoint 
    without modification.
    """

    teacher_example = CoverLetterWriterRequest(
        resume=TEACHER_RESUME,
        job_posting=TEACHER_JOB_POSTING,
        skills_to_highlight_from_resume="international teaching experience and my TESOL certification",
        tone=Tone.ASSERTIVE,
        company_name="Rocky Mountain High School"
    )
    engineer_example = CoverLetterWriterRequest(
        resume=AEROSPACE_RESUME,
        job_posting=SPACEX_JOB_POSTING,
        skills_to_highlight_from_resume="my experience with Python and my ability to work in a team",
        tone=Tone.FORMAL,
        company_name="SpaceX",
    )

    example_response = CoverLetterWriterExamplesResponse(
        example_names=["Highschool Teacher", "Aerospace Engineer"],
        examples=[teacher_example, engineer_example],
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=AIToolResponse, responses=error_responses)
async def cover_letter_writer(cover_letter_writer_request: CoverLetterWriterRequest):
    """
    **Generate a cover letter for a resume and job posting.**
    
    This method takes a resume and job posting as input and generates a cover letter for the resume and job posting.
    """
    user_prompt_postfix = f"\nHere is my resume to use as a reference when writing the cover letter: {cover_letter_writer_request.resume}"
    template_config = AITemplateModel(
        endpoint_name=ENDPOINT_NAME,
        ai_instructions=CoverLetterWriterInstructions(**cover_letter_writer_request.dict()),
        user_prompt_postfix=user_prompt_postfix,
        system_prompt=SYSTEM_PROMPT,
        frequency_penalty=1.3,
        presence_penalty=0.8,
        temperature=0.65,
        max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE
    )
    return get_ai_tool_response(template_config)
