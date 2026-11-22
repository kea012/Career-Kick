"""
AI Client Module
================

This module provides the `AIClient` class, which serves as a decoupled interface 
between the Career Kick application and the Google Gemini AI models. 

The primary goal of this client is to encapsulate the complexity of the Google 
Generative AI SDK, ensuring that the rest of the application interacts with the 
AI using high-level, type-safe methods rather than raw SDK calls.

Key Responsibilities:
1. API Key Management: Handles retrieval and sanitization of API keys.
2. Structured Output: Uses Pydantic models to force the AI to return valid JSON.
3. Multimodal Analysis: Supports combined text and PDF inputs for resume analysis.
4. Resilience: Implements exponential backoff retries to handle transient API failures.
"""
import os
import asyncio
import logging
from typing import Type, TypeVar, Optional
from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class AIClient:
    """
    A decoupled client for interacting with the Gemini AI model.
    
    This class wraps the Gemini SDK to provide specialized methods for 
    generating structured JSON responses and analyzing multimodal content (PDFs).
    
    Attributes:
        _api_key (Optional[str]): The sanitized Gemini API key.
        _model_name (Optional[str]): The identifier of the model being used (e.g., 'gemini-flash-latest').
        _client (genai.Client): The internal Google GenAI client instance.
    """

    _api_key: Optional[str]
    _model_name: Optional[str]

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initializes the AIClient.

        Args:
            api_key (Optional[str]): API key. If None, looks for GEMINI_API_KEY env var.
            model_name (Optional[str]): Model name. If None, defaults to 'gemini-flash-latest'.

        Raises:
            ValueError: If no API key is found in arguments or environment variables.
        """
        key = api_key or os.getenv("GEMINI_API_KEY")
        if key:
            # Strip common quotes and "smart quotes" often introduced by copy-pasting from docs
            self._api_key = key.strip(" \"' \u201c\u201d\u2018\u2019")
        else:
            self._api_key = None

        self._model_name = model_name or os.getenv("MODEL_NAME", "gemini-flash-latest")

        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please provide an API key in the constructor or set the GEMINI_API_KEY environment variable."
            )

        self._client = genai.Client(api_key=self._api_key, vertexai=False)

    async def generate_structured_response(
        self, system_instruction: str, user_message: str, response_model: Type[T]
    ) -> T:
        """
        Calls the AI model and automatically parses the output into the provided Pydantic model.

        This method utilizes the 'response_mime_type': 'application/json' configuration 
        to ensure the AI returns a valid JSON string that matches the schema of 
        the response_model.

        Args:
            system_instruction (str): The behavioral prompt defining the AI's role.
            user_message (str): The actual user query or input.
            response_model (Type[T]): A Pydantic class used for validation and parsing.

        Returns:
            T: An instance of the response_model populated with AI-generated data.

        Raises:
            Exception: If the AI call fails or the response cannot be parsed into the model.
        """

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        def sync_call():
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                ),
            )
            return response.text

        try:
            response_text = await asyncio.to_thread(sync_call)
            return response_model.model_validate_json(response_text)
        except Exception as e:
            logger.error(f"AI Model call or parsing failed: {e}")
            raise e

    async def generate_multimodal_response(
        self,
        system_instruction: str,
        user_message: str,
        file_bytes: bytes,
        mime_type: str = "application/pdf",
    ) -> str:
        """
        Handles multimodal inputs (Text + File) to analyze documents like resumes.

        Unlike the structured response, this method returns raw text as the AI's 
        analysis is typically conversational (e.g., feedback on a resume).

        Args:
            system_instruction (str): Instructions for the AI on how to analyze the document.
            user_message (str): The user's specific question about the document.
            file_bytes (bytes): The raw bytes of the uploaded file.
            mime_type (str): The MIME type of the file (defaults to 'application/pdf').

        Returns:
            str: The AI's natural language analysis of the provided file.

        Raises:
            Exception: If the multimodal AI call fails.
        """

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        def sync_call():
            # Create a Part for the file content
            file_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)

            response = self._client.models.generate_content(
                model=self._model_name,
                contents=[user_message, file_part],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            return response.text

        try:
            return await asyncio.to_thread(sync_call)
        except Exception as e:
            logger.error(f"Multimodal AI call failed: {e}")
            raise e
