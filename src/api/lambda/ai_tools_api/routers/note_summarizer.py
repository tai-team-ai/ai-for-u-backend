import logging
import os
from pathlib import Path
import sys
import threading
from typing import Optional
from fastapi import APIRouter, Response, status, Request
import openai
from pydantic import BaseModel, Field

sys.path.append(Path(__file__, "../utils").absolute())
from utils import initialize_openai, prepare_response, CamelCaseModel, log_to_s3

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

router = APIRouter()


class NoteSummarizerModel(CamelCaseModel):
    notes_to_summarize: str
    include_summary_sentence: Optional[bool] = True
    number_of_bullets: Optional[int] = 3
    number_of_action_items: Optional[int]

class NoteSummarizerResponseModel(CamelCaseModel):
    summary_sentence: Optional[str]
    bullet_points: Optional[str]
    action_items: Optional[str]


def get_openai_response(prompt: str) -> str:
    """
    Method uses openai model text-curie-001 to summarize notes.
    
    The method takes a string of notes and returns a summary of the notes. Optionally, 
    the number of action items and bullets can be specified. This method forwards notes with
    options to openai for processing. The response from openai is then returned to the client.

    :param prompt: Request containing notes and options for summarization.

    :return: response to prompt
    """
    initialize_openai()
    prompt_len = 500
    max_tokens = min(600, prompt_len / 1.3)
    logger.info(f"prompt: {prompt}")
    logger.info(f"max_tokens: {max_tokens}")
    openai_response = openai.Completion.create(
        engine="text-curie-001",
        prompt=prompt,
        temperature=0.0,
        max_tokens=int(max_tokens),
        top_p=1,
        frequency_penalty=0.4,
        presence_penalty=0,
        best_of=2,
        stream=False,
        logprobs=None,
        echo=False,
    )
    logger.info(f"openai response: {openai_response}")
    return openai_response.choices[0].text.strip()

@router.post("/note_summarizer", response_model=NoteSummarizerResponseModel, status_code=status.HTTP_200_OK)
async def note_summarizer(note_summarizer_request: NoteSummarizerModel, response: Response, request: Request):
    """
    Method uses openai model text-curie-001 to summarize notes.
    
    The method takes a string of notes and returns a summary of the notes. Optionally, 
    the number of action items and bullets can be specified. This method forwards notes with
    options to openai for processing. The response from openai is then returned to the client.

    :param note_summarizer: Request containing notes and options for summarization.
    :param response: Response object to add headers to.

    :return: Summary of notes 
    """
    logger.info(f"note_summarizer_request: {note_summarizer_request}")
    for field_name, value in note_summarizer_request:
        if isinstance(value, str):
            setattr(note_summarizer_request, field_name, value.strip())
    prepare_response(response, request)
    prompts = {}
    if note_summarizer_request.include_summary_sentence:
        prompts['summary_sentence'] = f"Summarize these notes in a few sentences:\n\n\"{note_summarizer_request.notes_to_summarize}\"\n"
    if note_summarizer_request.number_of_bullets > 0:
        prompts['bullet_points'] = f"Summarize these notes in {note_summarizer_request.number_of_bullets} bullet point:\n\n{note_summarizer_request.notes_to_summarize}\n\nBullet Point:\n1."
    if note_summarizer_request.number_of_action_items > 0:
        prompts['action_items'] = f"Create {note_summarizer_request.number_of_action_items} action item from these notes:"\
                        f"\n\n{note_summarizer_request.notes_to_summarize}\n\nAction Item(s):\n1."

    response_model = NoteSummarizerResponseModel(**prompts)

    threads = []
    for field_name, value in response_model:
        if not value:
            continue
        thread = threading.Thread(target=get_openai_response_thread_wrapper, args=(response_model, field_name, value))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()
    
    for field_name, value in response_model:
        # When there is only one bullet point or action item, openai returns a list of bullet points or action items instead of a single string.
        # This code handles that case and returns a single string instead of a list.
        if note_summarizer_request.number_of_bullets ==1 and field_name == 'bullet_points':
            value = value.split('\n')[0]
            setattr(response_model, field_name, value)
        if note_summarizer_request.number_of_action_items ==1 and field_name == 'action_items':
            value = value.split('\n')[0]
            setattr(response_model, field_name, value)
        if field_name == 'bullet_points' or field_name == 'action_items':
            setattr(response_model, field_name, f"1. {value}")

    logger.info(f"response_model: {response_model}")
    try:
        await log_to_s3(request, response, response_model, prompts)
    except Exception as e:
        logger.error(f"Error logging to s3: {e}")
    return response_model


def get_openai_response_thread_wrapper(response_model: NoteSummarizerResponseModel, field_name: str, prompt: str) -> None:
    """
    Wrapper method to call get_openai_response in a thread.

    :param response_model: Response model to update with openai response.
    :param prompts: Prompt to send to openai.

    :return: None
    """
    setattr(response_model, field_name, get_openai_response(prompt))

