import logging
import sys
from typing import Optional, List
from pathlib import Path
from pydantic import constr
from fastapi import APIRouter, Request, Response, status
sys.path.append(Path(__file__).parent / "../utils")
from utils import (
    CamelCaseModel,
    sanitize_string,
    BaseTemplateRequest,
    Tone,
    EXAMPLES_ENDPOINT_POSTFIX,
    docstring_parameter,
    ExamplesResponse
)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()

ENDPOINT_NAME = "cover-letter-writer"

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

@docstring_parameter(ENDPOINT_NAME)
class CoverLetterWriterRequest(BaseTemplateRequest):
    """
    **Define the model for the request body for {0} endpoint.**
    
    **Atrributes:**
    - resume: The resume to generate a cover letter for.
    - job_posting: The job posting to generate a cover letter for.
    - skills_to_highlight_from_resume: The skills to highlight from the resume.
    
    Inherits from BaseTemplateRequest:
    """
    
    __doc__ += BaseTemplateRequest.__doc__
    resume: constr(min_length=1, max_length=10000)
    job_posting: constr(min_length=1, max_length=10000)
    company_name: Optional[constr(min_length=1, max_length=50)] = None
    skills_to_highlight_from_resume: Optional[constr(min_length=1, max_length=10000)] = None


@docstring_parameter(ENDPOINT_NAME)
class CoverLetterWriterResponse(CamelCaseModel):
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
    examples: list[CoverLetterWriterResponse]


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


@router.post(f"/{ENDPOINT_NAME}", response_model=CoverLetterWriterResponse, status_code=status.HTTP_200_OK)
async def cover_letter_writer(request: Request, cover_letter_writer_request: CoverLetterWriterRequest):
    """
    **Generate a cover letter for a resume and job posting.**
    
    This method takes a resume and job posting as input and generates a cover letter for the resume and job posting.
    """
    return CoverLetterWriterResponse(cover_letter="This is a perfect cover letter.")
