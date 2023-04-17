import logging
import sys
import os
from typing import Optional, List
from pathlib import Path
from pydantic import constr, Field
from fastapi import APIRouter, Request, Response, status
sys.path.append(Path(__file__).parent / "../utils")
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../gpt_turbo"))
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response
from utils import (
    AIToolModel,
    sanitize_string,
    BaseAIInstructionModel,
    Tone,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse,
    AIToolsEndpointName,
    UUID_HEADER_NAME,
    BASE_USER_PROMPT_PREFIX,
    append_field_prompts_to_prompt,
    error_responses,
    TOKEN_EXHAUSTED_JSON_RESPONSE,
    TokensExhaustedException,
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = AIToolsEndpointName.COVER_LETTER_WRITER.value
MAX_TOKENS_FROM_GPT_RESPONSE = 400

RESUME_EXAMPLE = """
Name: John Doe

Education: 
- Bachelor of Arts in English Literature, University of California, Los Angeles
- Master of Education in Teaching English as a Second Language, University of Southern California

Experience: 
- English Teacher, XYZ High School, Los Angeles, 2015-2020
     - Developed and implemented lesson plans for 9th-12th grade English classes, resulting in an average improvement of 30% in student test scores
     - Led a poetry club for students, resulting in several students being published in local literary magazines
     - Coordinated with other teachers and administrators to create a school-wide reading initiative, resulting in increased student engagement and a positive school culture

- English Instructor, ABC Language School, Tokyo, Japan, 2010-2015
     - Taught English as a Second Language to students of all ages and levels, including business professionals and children
     - Designed and implemented curriculum for specialized courses such as Business English and TOEFL preparation
     - Conducted parent-teacher conferences and provided individualized feedback and progress reports for each student

Skills: 
- Excellent communication and interpersonal skills
- Creative and innovative lesson planning and delivery
- Strong understanding of English literature and grammar
- Proficient in Microsoft Office and Google Suite

Certifications: 
- California Teaching Credential in English, 2015
- TESOL Certification, 2010

Professional Memberships: 
- National Council of Teachers of English
- TESOL International Association

References: 
Available upon request.
"""

JOB_POSTING_EXAMPLE = """
Job Title: High School Teacher

Job Type: Full-time

Location: Rocky Mountain High School, Los Angeles, CA

Are you passionate about education and working with young minds? Do you have a strong desire to help shape the future of our youth? If so, we are looking for a highly motivated and dynamic individual to join our team as a high school teacher.

Responsibilities:

- Develop and implement lesson plans that align with state and national standards
- Create a positive and engaging learning environment for students
- Assess student progress and provide timely feedback
- Collaborate with other teachers and staff to support student success
- Participate in professional development opportunities to stay current on best practices and teaching strategies
- Maintain accurate records and communicate with parents/guardians as needed

Requirements:

- Bachelor's degree in Education or related field
- State teaching certification or eligibility to obtain certification
- Strong communication and interpersonal skills
- Ability to work collaboratively with colleagues and administrators
- Passion for working with high school students and helping them reach their full potential

We offer a competitive salary and benefits package, as well as ongoing professional development opportunities. If you are interested in joining our team and making a positive impact on the lives of our students, please submit your resume and cover letter for consideration.
"""


AI_PURPOSE = " ".join(ENDPOINT_NAME.split("-")).lower()
@docstring_parameter(AI_PURPOSE, [tone.value for tone in Tone])
class CoverLetterWriterInsructions(BaseAIInstructionModel):
    """You are an expert {0}. I will provide a resume, job posting, and company name (if given) to write a cover letter for.

    I will also provide a list of skills to highlight from the resume. You should respond with a cover letter that is tailored to the job posting and company, highlights the my skills, and demonstrates enthusiasm for the company and role.

    If you do not feel like that the job isn't a good fit for me, you should do your best to highlight the skills that you think are most relevant to the job posting in addition to the ones I have asked to highlight.

    **Instructions that I may provide you to assist you as you write my cover letter:**
    * job_posting: The job posting to generate a cover letter for.
    * company_name: The name of the company you are applying to.
    * skills_to_highlight_from_resume: The skills to highlight from the resume. If this is not provided, you should highlight the skills that you think are most relevant to the job posting or most impressive if the skills do not directly align with the job description..
    * tone: The tone that you should use when writing the cover letter. Here are the possible tones: {1}.
    * resume: The resume to use when writing the cover letter. This is guaranteed to be provided.
    """
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
        description="The skills to highlight form your resume. What's your best skills?",
    )
    tone: Optional[Tone] = Field(
        default=Tone.ASSERTIVE,
        title="Tone of the Cover Letter",
        description="The tone used when writing the cover letter.",
    )

SYSTEM_PROMPT = CoverLetterWriterInsructions.__doc__

@docstring_parameter(ENDPOINT_NAME)
class CoverLetterWriterRequest(CoverLetterWriterInsructions):
    """
    **Define the model for the request body for {0} endpoint.**
    
    **Atrributes:**
    - resume: The resume to generate a cover letter for.
    - job_posting: The job posting to generate a cover letter for.
    - skills_to_highlight_from_resume: The skills to highlight from the resume.

    **AI Instructions:**

    """
    
    __doc__ += CoverLetterWriterInsructions.__doc__
    resume: constr(min_length=1, max_length=10000) = Field(
        ...,
        title="Resume",
        description="Your resume. Don't worry too much if the formatting isn't perfect.",
    )



@docstring_parameter(ENDPOINT_NAME)
class CoverLetterWriterResponse(AIToolModel):
    """
    **Define the model for the response body for {0} endpoint.**
    
    **Atrributes:**
    - cover_letter: The cover letter generated for the resume and job posting.
    """

    cover_letter: str


@docstring_parameter(ENDPOINT_NAME)
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

    cover_letter_example = CoverLetterWriterRequest(
        resume=RESUME_EXAMPLE,
        job_posting=JOB_POSTING_EXAMPLE,
        skills_to_highlight_from_resume="international teaching experience and my TESOL certification",
        tone=Tone.ASSERTIVE,
        freeform_command="Please don't talk about my lack of experience teaching high school students.",
        company_name="Rocky Mountain High School"
    )

    example_response = CoverLetterWriterExamplesResponse(
        example_names=["Highschool Teacher Cover Letter"],
        examples=[cover_letter_example]
    )
    return example_response


@router.post(f"/{ENDPOINT_NAME}", response_model=CoverLetterWriterResponse, responses=error_responses)
async def cover_letter_writer(request: Request, cover_letter_writer_request: CoverLetterWriterRequest):
    """
    **Generate a cover letter for a resume and job posting.**
    
    This method takes a resume and job posting as input and generates a cover letter for the resume and job posting.
    """
    logger.info(f"Received request for {ENDPOINT_NAME} endpoint.")
    user_prompt = append_field_prompts_to_prompt(CoverLetterWriterInsructions(**cover_letter_writer_request.dict()), BASE_USER_PROMPT_PREFIX)
    user_prompt += f"\nHere is my resume you should use as reference: {cover_letter_writer_request.resume}"
    uuid = request.headers.get(UUID_HEADER_NAME)
    user_chat = GPTTurboChat(
        role=Role.USER,
        content=user_prompt
    )
    try:
        chat_session = get_gpt_turbo_response(
            system_prompt=SYSTEM_PROMPT,
            chat_session=GPTTurboChatSession(messages=[user_chat]),
            frequency_penalty=0.0,
            presence_penalty=0.0,
            temperature=0.3,
            uuid=uuid,
            max_tokens=MAX_TOKENS_FROM_GPT_RESPONSE
        )
    except TokensExhaustedException:
        return TOKEN_EXHAUSTED_JSON_RESPONSE

    latest_gpt_chat_model = chat_session.messages[-1]
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)

    response_model = CoverLetterWriterResponse(
        cover_letter=latest_chat
    )
    logger.info(f"Returning response for {ENDPOINT_NAME} endpoint.")
    return response_model
