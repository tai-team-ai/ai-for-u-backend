import logging
import os
from pathlib import Path
import sys
import threading
from typing import Optional
from fastapi import APIRouter, Response, status, Request
import openai

from pydantic import conint, Field


sys.path.append(Path(__file__, "../").absolute())
from gpt_turbo import GPTTurboChatSession, GPTTurboChat, Role, get_gpt_turbo_response
from utils import (
    AIToolModel,
    BaseAIInstructionModel,
    UUID_HEADER_NAME,
    update_user_token_count,
    sanitize_string,
    EXAMPLES_ENDPOINT_POSTFIX,
    ExamplesResponse,
    BASE_USER_PROMPT_PREFIX,
    error_responses,
    TOKEN_EXHAUSTED_JSON_RESPONSE,
    TokensExhaustedException,
    AIToolResponse,
)

router = APIRouter()

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

TEXT_BOOK_EXAMPLE = """
Chinchillas are small, furry rodents that are native to the Andes Mountains in South America. They are known for their adorable appearance, with their big ears, fluffy tails, and soft, dense fur. Chinchillas are highly social animals and are often kept as pets, but they require a lot of care and attention.

One of the most interesting things about chinchillas is their fur. Their fur is so dense that it can prevent water from reaching their skin, which is why they take dust baths to keep their fur clean and healthy. In fact, chinchillas have the densest fur of any mammal, with up to 80 hairs growing from a single hair follicle! Their fur is also highly sought after by the fashion industry, which has led to a decline in wild populations.

Chinchillas are herbivores and eat a diet that consists mainly of hay, pellets, and fresh vegetables. They have a unique digestive system that requires them to eat a lot of roughage to keep their teeth from overgrowing. Chinchillas are also known for their jumping abilities, which they use to navigate the rocky terrain of their native habitat. Overall, chinchillas are fascinating creatures that make great pets for those who are willing to put in the time and effort to care for them properly.
"""

TRANSCRIPT_EXAMPLE = """
0:00
Hi everyone! My name is Jessica and I'm a photographer who has been fortunate enough to travel around the world and capture some truly amazing cultures and people.

0:05
One of my favorite trips was to India, where I spent weeks exploring the vibrant streets and capturing the colorful festivals that take place throughout the year.

0:10
I also had the opportunity to visit remote villages in Africa, where I was welcomed with open arms by the locals and given the chance to document their daily lives.

0:15
In Japan, I was amazed by the intricate details of the architecture and the beauty of the cherry blossom trees that lined the streets.

0:20
I've also been to South America, where I was blown away by the stunning landscapes and the warmth of the people.

0:25
But perhaps the most memorable experience was when I visited a tribe in the Amazon rainforest. I was completely immersed in their way of life, learning about their customs and traditions, and capturing some truly unique moments.

0:30
Overall, my travels have taught me so much about different cultures and ways of life. It's been an incredible journey that I feel so grateful for.

0:35
I've also been able to share my work with others through exhibitions and publications, which has been a really rewarding experience.

0:40
For me, photography is not just about taking pretty pictures. It's about connecting with people and telling their stories.

0:45
I hope that my work inspires others to explore the world and open their hearts to different cultures and experiences.

0:50
Because at the end of the day, it's these connections that make life truly meaningful.

0:55
Thank you for listening and I hope you enjoyed hearing about my adventures as a photographer.

1:00
If you have any questions or comments, feel free to leave them below and I'll do my best to respond.

1:05
And if you're interested in seeing more of my work, you can check out my website or follow me on social media.

1:10
Thanks again and happy travels!

1:15
[background music]

1:20
[End of video]
"""

ARTICLE_EXAMPLE = """
---

The Benefits of Mindfulness and Meditation for Mental Health

In today's fast-paced world, it's easy to get caught up in the hustle and bustle of our daily lives. We often find ourselves juggling multiple tasks and responsibilities, which can lead to stress, anxiety, and other mental health issues. That's where mindfulness and meditation come in - two practices that can have a profound impact on our mental well-being.

What is mindfulness?

Mindfulness is the practice of being present in the moment and fully engaged with our surroundings. It involves paying attention to our thoughts, feelings, and physical sensations without judgment, and accepting them for what they are. By doing so, we can learn to be more aware of our emotions and respond to them in a healthy way.

What is meditation?

Meditation is a technique that involves focusing your attention on a specific object, thought, or activity to achieve a state of calmness and relaxation. It can be done in various forms, such as breathing exercises, visualization, or guided meditation. By training your mind to focus on the present moment, you can reduce stress and anxiety and increase feelings of happiness and well-being.

How do mindfulness and meditation benefit mental health?

Numerous studies have shown that mindfulness and meditation can have a positive impact on mental health. Here are some of the benefits they offer:

1. Reducing stress and anxiety: Mindfulness and meditation have been shown to lower cortisol levels, a hormone associated with stress. By reducing stress and anxiety, you can improve your overall sense of well-being.

2. Lowering symptoms of depression: Meditation has been shown to increase activity in the prefrontal cortex, an area of the brain associated with positive emotions. This can help reduce symptoms of depression and increase feelings of happiness.

3. Improving sleep: Mindfulness and meditation can help you relax and fall asleep more easily. By reducing racing thoughts and promoting relaxation, you can enjoy a better quality of sleep.

4. Boosting cognitive function: Mindfulness and meditation can improve cognitive function, including attention, memory, and decision-making. By training your brain to focus on the present moment, you can increase your ability to concentrate and perform tasks more efficiently.

5. Enhancing self-awareness: Mindfulness and meditation can help you become more aware of your thoughts, feelings, and behaviors. By doing so, you can identify negative patterns and make positive changes in your life.

How to incorporate mindfulness and meditation into your daily routine?

Incorporating mindfulness and meditation into your daily routine can be easy and rewarding. Here are some tips to get started:

1. Start small: Begin with just a few minutes of mindfulness or meditation each day, and gradually increase the time as you become more comfortable.

2. Find a quiet space: Choose a quiet, comfortable space where you can focus without distractions.

3. Use guided meditations: If you're new to meditation, try using guided meditations to help you stay focused and relaxed.

4. Practice regularly: Consistency is key when it comes to mindfulness and meditation. Try to practice every day, even if it's just for a few minutes.

In conclusion, mindfulness and meditation can be powerful tools for improving mental health and well-being. By incorporating these practices into your daily routine, you can reduce stress, increase happiness, and enjoy a better quality of life.
"""


MAX_TOKENS_FROM_GPT_RESPONSE = 400

SYSTEM_PROMPT = (
    "You are a professional text summarizer. You job is to summarize the text in markdown format for me in order to help me "
    "understand the text better and allow me to understand the information quickly without having to read the entire text myself. "
    "I may request for a summary sentence, bullet points, and/or actions to be generated from the text."
    "You should only respond with the sections that I specify in my request, nothing else. You should use markdown format "
    "and should use bold titles for each section. By using markdown, you will help me organize the information better."
)

ENDPOINT_NAME = "text-summarizer"


class TextSummarizerRequest(BaseAIInstructionModel):
    """
    **Define the request model for the text summarizer endpoint.**
    
    **Attributes:**
    - text_to_summarize: text for the endpoint to summarize
    - include_summary_sentence: whether or not to include a summary sentence in the response
    - number_of_bullets: number of bullet points to include in the response
    - number_of_action_items: number of action items to include in the response (this is suggested to use with 
        summaries of things such as meeting minutes)
    
    Inherit from BaseAIInstructionModel:    
    """
    __doc__ += BaseAIInstructionModel.__doc__
    text_to_summarize: str = Field(
        ...,
        title="Text to Summarize",
        description="The text that you wanted summarized. (e.g. articles, notes, transcripts, etc.)",
    )
    include_summary_sentence: Optional[bool] = Field(
        default=True,
        title="Include Summary Sentence",
        description="Whether or not to include a summary sentence in the response.",
    )
    number_of_bullets: Optional[conint(ge=0, le=8)] = Field(
        default=3,
        title="Number of Bullets",
        description="The number of bullet points to include in the response.",
    )
    number_of_action_items: Optional[conint(ge=0, le=8)] = Field(
        default=0,
        title="Number of Action Items",
        description="The number of action items to include in the response. Action items are often applicable for meeting notes, lectures, etc.",
    )

class TextSummarizerExampleResponse(ExamplesResponse):
    examples: list[TextSummarizerRequest]
    
    
@router.get(f"/{ENDPOINT_NAME}-{EXAMPLES_ENDPOINT_POSTFIX}", response_model=TextSummarizerExampleResponse, status_code=status.HTTP_200_OK)
async def sandbox_chatgpt_examples() -> TextSummarizerExampleResponse:
    """Return examples for the text summarizer endpoint."""
    examples = [
        TextSummarizerRequest(
            text_to_summarize=TEXT_BOOK_EXAMPLE,
            include_summary_sentence=True,
            number_of_bullets=5,
            number_of_action_items=2,
        ),
        TextSummarizerRequest(
            text_to_summarize=TRANSCRIPT_EXAMPLE,
            include_summary_sentence=True,
            number_of_bullets=3,
            number_of_action_items=0,
        ),
        TextSummarizerRequest(
            text_to_summarize=ARTICLE_EXAMPLE,
            include_summary_sentence=True,
            number_of_bullets=6,
            number_of_action_items=3,
        ),
    ]
    response = TextSummarizerExampleResponse(
        example_names=["Text Book", "Transcript", "Article"],
        examples=examples
    )
    return response

@router.post(f"/{ENDPOINT_NAME}", response_model=AIToolResponse, responses=error_responses)
async def text_summarizer(text_summarizer_request: TextSummarizerRequest, request: Request):
    """**Summarize text using GPT-3.**"""
    logger.info(f"Received request: {text_summarizer_request}")
    for field_name, value in text_summarizer_request:
        if isinstance(value, str):
            setattr(text_summarizer_request, field_name, value.strip())
    user_prompt = BASE_USER_PROMPT_PREFIX
    if text_summarizer_request.include_summary_sentence:
        user_prompt += f"Please provide me with a summary sentance.\n"
    if text_summarizer_request.number_of_bullets:
        user_prompt += f"Please provide me with {text_summarizer_request.number_of_bullets} bullet points.\n"
    if text_summarizer_request.number_of_action_items:
        user_prompt += f"Please provide me with {text_summarizer_request.number_of_action_items} action items.\n"

    user_prompt += "Finally, here's the text I want you to summarize: " + text_summarizer_request.text_to_summarize

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
    update_user_token_count(uuid, latest_gpt_chat_model.token_count)
    latest_chat = latest_gpt_chat_model.content
    latest_chat = sanitize_string(latest_chat)

    response_model = AIToolResponse(
        response=latest_chat,
    )
    logger.info(f"Returning response for {ENDPOINT_NAME} endpoint.")
    return response_model
