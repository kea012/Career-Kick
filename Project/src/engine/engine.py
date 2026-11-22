"""
Career Engine Module
====================

This module implements the core orchestration logic for the Career Kick application. 
The `CareerEngine` acts as the 'brain' of the system, coordinating between the 
AI Client (for intent extraction) and the Storage Repositories (for data persistence 
and retrieval).

Architecture:
1. Intent Extraction: The engine uses a specialized system prompt to turn unstructured 
   user input into a typed `ExtractionResult`. This includes both the intent 
   identification and a 'reflection' step to check if all required data is present.
2. Validation: The engine performs early returns if the AI indicates the request 
   is incomplete or if required files (e.g., PDF for resume FAQ) are missing.
3. Dispatch: Based on the identified intent, the engine routes the request to the 
   appropriate repository method or a multimodal AI call.

This design ensures that the interface layer remains thin and the storage layer 
remains decoupled from the AI's prompt logic.
"""
import logging
from typing import Dict, Any, Optional
from src.engine.models import ExtractionResult, EngineResponse
from src.engine.ai_client import AIClient
from src.storage.repositories import MemberRepository, JobRepository
from src.storage.database import MemberSessionLocal, JobsSessionLocal

logger = logging.getLogger(__name__)

# --- Production Optimized Prompt ---
# We combine Extraction (what does the user want?) and Reflection (do we have 
# enough info to do it?) into a single AI pass. This reduces latency and API 
# costs by avoiding multiple round-trips to the model.
_SYSTEM_PROMPT = """
You are the orchestrator for Career Kick. Your goal is to analyze user input and provide a structured extraction and completeness check in ONE step.

Intents: 
- 'resume faq': User has a question about their uploaded resume.
- 'register profile': User wants to create a professional profile.
- 'get profiles': User wants to see ALL registered members.
- 'search profiles': User wants to find specific members using a keyword (e.g., "someone in history", "find a cook").
- 'get jobs': User wants to see ALL open job listings.
- 'search jobs': User wants to find jobs using a keyword (e.g., "jobs related to cooking", "Python roles").
- 'find similar jobs': User wants jobs matching THEIR OWN background. THIS REQUIRES the user's email to retrieve their profile first.
- 'find similar colleagues': User wants to find peers similar to THEMSELVES. THIS REQUIRES the user's email to retrieve their profile first.
- 'delete': User wants to remove their profile.
- 'unknown': Request is unrelated to career/resume services.

Rules:
1. Extraction: Identify the intent and extract all relevant data (e.g., email, full_name, major, keyword).
2. Reflection: Immediately determine if the data is complete for that intent.
   - 'resume faq' requires: No specific data fields, but a file must be present.
   - 'register profile' requires: full_name, email, headline, major, years_experience.
   - 'search profiles' requires: keyword.
   - 'search jobs' requires: keyword.
   - 'find similar jobs' and 'find similar colleagues' require: email.
   - 'delete' requires: email.
3. CRITICAL LOGIC FOR UNREGISTERED USERS:
   - If a user asks to "find", "search", or "give me" a person or job, but DOES NOT provide an email address, you MUST use the 'search profiles' or 'search jobs' intent.
   - NEVER use 'find similar' intents unless the user has explicitly provided an email or is clearly referring to their own registered account.
   - If the user is just browsing, they are an unregistered guest; use the keyword-based 'search' intents.
4. Output: Return a JSON object containing 'intent', 'data', 'is_complete', and 'missing_fields'.
"""


class CareerEngine:
    """
    The production-grade orchestration engine for Career Kick.
    
    Handles the request lifecycle from AI-driven intent extraction to 
    storage dispatch and final response formatting.
    
    Attributes:
        ai_client (AIClient): Client for interacting with Gemini AI.
        member_repo (MemberRepository): Repository for managing user profiles.
        job_repo (JobRepository): Repository for managing job listings.
    """

    def __init__(
        self,
        ai_client: AIClient,
        member_repo: MemberRepository,
        job_repo: JobRepository,
    ):
        """Initializes the engine with its required dependencies."""
        self.ai_client = ai_client
        self.member_repo = member_repo
        self.job_repo = job_repo

    async def process_request(
        self,
        user_input: str,
        file_bytes: Optional[bytes] = None,
        mime_type: str = "application/pdf",
    ) -> EngineResponse:
        """
        The main entry point for processing any user request.
        
        This method implements the core pipeline:
        1. Extract intent and required data using AI.
        2. Validate that all requirements (data and files) are met.
        3. Dispatch to the appropriate handler.

        Args:
            user_input (str): The raw text entered by the user.
            file_bytes (Optional[bytes]): Optional PDF bytes for resume analysis.
            mime_type (str): The MIME type of the uploaded file.

        Returns:
            EngineResponse: A standardized response containing status, message, and optional data.
        """
        try:
            # --- STEP 1: UNIFIED EXTRACTION & REFLECTION ---
            # We ask the AI to not only identify the intent but also tell us if 
            # the user provided enough information to fulfill it.
            extraction = await self.ai_client.generate_structured_response(
                system_instruction=_SYSTEM_PROMPT,
                user_message=user_input,
                response_model=ExtractionResult,
            )

            # Special Case: The user uploaded a resume but hasn't asked a question yet.
            # We acknowledge the upload and prompt them for a query.
            if file_bytes and extraction.intent == "unknown":
                return EngineResponse(
                    status="success",
                    message="Resume uploaded successfully! What would you like to know about your resume?",
                    data=None,
                )

            # --- STEP 2: EARLY RETURN FOR INCOMPLETE DATA ---
            
            # 1. Multimodal Requirement: 'resume faq' requires a PDF file.
            if extraction.intent == "resume faq" and not file_bytes:
                return EngineResponse(
                    status="incomplete",
                    message="Please upload your resume in PDF format to ask questions about it.",
                    data={"missing": ["resume_pdf"]},
                )

            # 2. Format Validation: Ensure the uploaded file is actually a PDF.
            if file_bytes and mime_type != "application/pdf":
                return EngineResponse(
                    status="incomplete",
                    message="resume uploaded must be in pdf format",
                    data={"missing": ["valid_pdf"]},
                )

            # 3. General Data Completeness: If AI marked is_complete=False, we stop here.
            if not extraction.is_complete:
                return EngineResponse(
                    status="incomplete",
                    message="Please provide the missing information.",
                    data={"missing": extraction.missing_fields},
                )

            # --- STEP 3: TYPE-SAFE DISPATCH ---
            # All requirements are met; proceed to execute the intent.
            return await self._dispatch(extraction, user_input, file_bytes, mime_type)

        except Exception as e:
            logger.exception(f"Critical Engine error: {e}")
            return EngineResponse(status="error", message=str(e))

    async def _dispatch(
        self,
        extraction: ExtractionResult,
        user_input: str,
        file_bytes: Optional[bytes] = None,
        mime_type: str = "application/pdf",
    ) -> EngineResponse:
        """
        Internal dispatcher that maps intents to storage or AI operations.
        
        Args:
            extraction (ExtractionResult): The result of the AI's intent analysis.
            user_input (str): The original user message.
            file_bytes (Optional[bytes]): The PDF content if available.
            mime_type (str): The MIME type of the file.

        Returns:
            EngineResponse: The result of the dispatched operation.
        """
        intent = extraction.intent
        data = extraction.data

        if intent == "resume faq":
            # This functionality is purely AI-driven (Stateless) as per CONTRACT.md.
            # We use a specialized career coach prompt for the multimodal call.
            resume_prompt = "You are an expert career coach. Analyze the provided resume PDF and answer the user's question accurately and professionally. IMPORTANT: You only respond to queries about careers, resumes, and professional development. If the question is unrelated to these topics, politely decline and state that you are a career assistant."
            try:
                if file_bytes is None:
                    raise ValueError("File bytes are required for multimodal response")

                answer = await self.ai_client.generate_multimodal_response(
                    system_instruction=resume_prompt,
                    user_message=user_input,
                    file_bytes=file_bytes,
                    mime_type=mime_type,
                )
                return EngineResponse(
                    status="success", message=answer, data={"answer": answer}
                )
            except Exception as e:
                logger.error(f"Resume analysis failed: {e}")
                return EngineResponse(
                    status="error", message="Failed to analyze the resume PDF."
                )

        elif intent == "register profile":
            # Persist the user's professional profile to the member database.
            async with MemberSessionLocal() as session:
                reg_result = await self.member_repo.store_profile(session, data)
                return EngineResponse(status="success", message=reg_result)

        elif intent == "get profiles":
            # Retrieve a full list of all registered professional profiles.
            async with MemberSessionLocal() as session:
                profiles_result = await self.member_repo.get_all_profiles(session)
                return EngineResponse(
                    status="success",
                    message="Profiles retrieved successfully",
                    data=profiles_result,
                )

        elif intent == "search profiles":
            # Keyword-based search across names, majors, and headlines.
            keyword = data.get("keyword")
            if not keyword:
                return EngineResponse(
                    status="incomplete",
                    message="Please provide a search keyword.",
                    data={"missing": ["keyword"]},
                )

            async with MemberSessionLocal() as session:
                profiles = await self.member_repo.search_members(session, keyword)
                if not profiles:
                    return EngineResponse(
                        status="success",
                        message="There are currently no profiles related to this",
                        data=[],
                    )
                return EngineResponse(
                    status="success",
                    message=f"Found profiles related to '{keyword}'",
                    data=profiles,
                )

        elif intent == "get jobs":
            # Retrieve a full list of all available job listings.
            async with JobsSessionLocal() as session:
                jobs_list = await self.job_repo.get_all_jobs(session)
                if not jobs_list:
                    return EngineResponse(
                        status="success",
                        message="No jobs can be found at the moment",
                        data=[],
                    )
                return EngineResponse(
                    status="success",
                    message="Jobs retrieved successfully",
                    data=jobs_list,
                )

        elif intent == "search jobs":
            # Keyword-based search across job titles and descriptions.
            keyword = data.get("keyword")
            if not keyword:
                return EngineResponse(
                    status="incomplete",
                    message="Please provide a search keyword.",
                    data={"missing": ["keyword"]},
                )

            async with JobsSessionLocal() as jobs_session:
                jobs_found = await self.job_repo.query_listings(
                    jobs_session, {"keyword": keyword}
                )
                if not jobs_found:
                    return EngineResponse(
                        status="success",
                        message="No jobs can be found at the moment",
                        data=[],
                    )
                return EngineResponse(
                    status="success",
                    message=f"Found jobs related to '{keyword}'",
                    data=jobs_found,
                )

        elif intent == "find similar jobs":
            # Two-step flow: 1. Get User Profile -> 2. Use profile data to search jobs.
            email = data.get("email")
            if not email:
                return EngineResponse(
                    status="incomplete",
                    message="Please provide your email to find similar jobs.",
                    data={"missing": ["email"]},
                )

            async with MemberSessionLocal() as session:
                user_context = await self.member_repo.retrieve_context(session, email)
                if not user_context:
                    return EngineResponse(
                        status="success",
                        message="No profile found, returning empty job list",
                        data=[],
                    )

                # Extract major or headline to use as a search keyword for jobs.
                major = getattr(user_context, "major", None) or (
                    user_context.get("major")
                    if isinstance(user_context, dict)
                    else None
                )
                headline = getattr(user_context, "headline", None) or (
                    user_context.get("headline")
                    if isinstance(user_context, dict)
                    else None
                )
                search_keyword = major or headline

                if not search_keyword:
                    return EngineResponse(
                        status="success",
                        message="No profile data available to find similar jobs",
                        data=[],
                    )

                async with JobsSessionLocal() as jobs_session:
                    similar_jobs = await self.job_repo.query_listings(
                        jobs_session, {"keyword": search_keyword}
                    )
                    if not similar_jobs:
                        return EngineResponse(
                            status="success",
                            message="No jobs can be found at the moment",
                            data=[],
                        )
                    return EngineResponse(
                        status="success",
                        message=f"Found jobs similar to your background in {search_keyword}",
                        data=similar_jobs,
                    )

        elif intent == "find similar colleagues":
            # Two-step flow: 1. Get User Profile -> 2. Search for other users with the same major.
            email = data.get("email")
            if not email:
                return EngineResponse(
                    status="incomplete",
                    message="Please provide your email to find similar colleagues.",
                    data={"missing": ["email"]},
                )

            async with MemberSessionLocal() as session:
                user_context = await self.member_repo.retrieve_context(session, email)
                if not user_context:
                    return EngineResponse(
                        status="success",
                        message="No profile found, returning empty colleague list",
                        data=[],
                    )

                major = getattr(user_context, "major", None) or (
                    user_context.get("major")
                    if isinstance(user_context, dict)
                    else None
                )
                criteria = {"major": major if major is not None else "", "email": email}
                colleagues = await self.member_repo.query_similar(session, criteria)
                return EngineResponse(
                    status="success",
                    message="Found colleagues with similar backgrounds",
                    data=colleagues,
                )

        elif intent == "delete":
            # Remove the user's profile from the member database.
            email = data.get("email")
            if not email:
                return EngineResponse(
                    status="incomplete",
                    message="Please provide your email to delete your profile.",
                    data={"missing": ["email"]},
                )

            async with MemberSessionLocal() as session:
                del_result = await self.member_repo.delete(session, email)
                return EngineResponse(status="success", message=del_result)

        else:
            # Fallback for intents that the AI identified but the engine doesn't support.
            return EngineResponse(
                status="unknown",
                message="I'm sorry, I can only help with resume quality, career advice, or profile management.",
            )


# --- BACKWARD COMPATIBILITY LAYER ---
# These instances allow the legacy interface to call process_request() 
# without manually managing dependencies.
_default_ai_client = AIClient()
_default_member_repo = MemberRepository()
_default_job_repo = JobRepository()
_engine_instance = CareerEngine(
    _default_ai_client, _default_member_repo, _default_job_repo
)


async def process_request(user_input: str) -> Dict[str, Any]:
    """
    Legacy wrapper to maintain compatibility with existing interface layer.
    Returns a dictionary instead of an EngineResponse object.
    """
    response = await _engine_instance.process_request(user_input)
    return response.model_dump()
