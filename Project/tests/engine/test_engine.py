"""
Engine Unit Tests
=================

These tests verify the orchestration logic within the `CareerEngine`. 
To keep tests fast and deterministic, the AI Client and Storage 
Repositories are mocked using `unittest.mock.AsyncMock`.

Test Coverage:
1. Profile Registration: Success and duplicate email paths.
2. Member/Job Retrieval: Basic listing success paths.
3. Intent Handling: Proper response for 'unknown' intents.
4. Similarity Flow: Correct retrieval of profiles to drive job/peer searches.
5. Resume FAQ: Validation of multimodal AI calls and file-presence checks.
6. Edge Cases: Invalid file types, malformed AI responses, and empty results.
"""
import pytest
import os
from unittest.mock import AsyncMock, ANY, patch
from src.engine.engine import CareerEngine
from src.engine.ai_client import AIClient
from src.engine.models import ExtractionResult
from src.storage.repositories import MemberRepository, JobRepository


@pytest.fixture
def mock_ai_client():
    """Provides a mocked AI client that can be injected into the engine."""
    client = AsyncMock(spec=AIClient)
    return client


@pytest.fixture
def mock_member_repo():
    """Provides a mocked MemberRepository."""
    return AsyncMock(spec=MemberRepository)


@pytest.fixture
def mock_job_repo():
    """Provides a mocked JobRepository."""
    return AsyncMock(spec=JobRepository)


@pytest.fixture
def engine(mock_ai_client, mock_member_repo, mock_job_repo):
    """Provides a CareerEngine instance with mocked dependencies injected."""
    return CareerEngine(
        ai_client=mock_ai_client, member_repo=mock_member_repo, job_repo=mock_job_repo
    )


@pytest.mark.asyncio
async def test_register_profile_success(engine, mock_ai_client, mock_member_repo):
    """
    Scenario: Successful Registration.
    Verifies that when AI identifies 'register profile' and data is complete, 
    the engine calls the member repository to store the profile.
    """
    mock_extraction = ExtractionResult(
        intent="register profile",
        data={
            "full_name": "Test User",
            "email": "test@example.com",
            "headline": "Developer",
            "major": "CS",
            "years_experience": 2,
        },
        is_complete=True,
        missing_fields=[],
    )

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.store_profile.return_value = "profile_active"

    response = await engine.process_request("I want to register my profile...")

    assert response.status == "success"
    assert response.message == "profile_active"
    mock_member_repo.store_profile.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_profile_success(engine, mock_ai_client, mock_member_repo):
    """
    Scenario: Duplicate Email Registration.
    Verifies that the engine correctly forwards the 'already_registered' 
    status from the repository to the user.
    """
    mock_extraction = ExtractionResult(
        intent="register profile",
        data={
            "email": "exists@example.com",
            "full_name": "Ex",
            "headline": "H",
            "major": "M",
            "years_experience": 1,
        },
        is_complete=True,
        missing_fields=[],
    )

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.store_profile.return_value = "already_registered"

    response = await engine.process_request("Register me again")
    assert response.status == "success"
    assert response.message == "already_registered"


@pytest.mark.asyncio
async def test_get_members_success(engine, mock_ai_client, mock_member_repo):
    """
    Scenario: Retrieve all members.
    Verifies the 'get profiles' intent flow.
    """
    mock_extraction = ExtractionResult(
        intent="get profiles", data={}, is_complete=True, missing_fields=[]
    )
    mock_members = [{"full_name": "User 1", "email": "u1@ex.com"}]

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.get_all_profiles.return_value = mock_members

    response = await engine.process_request("Show me all members")
    assert response.status == "success"
    assert response.data == mock_members


@pytest.mark.asyncio
async def test_get_jobs_success(engine, mock_ai_client, mock_job_repo):
    """
    Scenario: Retrieve all jobs.
    Verifies the 'get jobs' intent flow.
    """
    mock_extraction = ExtractionResult(
        intent="get jobs", data={}, is_complete=True, missing_fields=[]
    )
    mock_jobs = [{"job_title": "SRE", "company_name": "CloudX"}]

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_job_repo.get_all_jobs.return_value = mock_jobs

    response = await engine.process_request("Find me some jobs")
    assert response.status == "success"
    assert response.data == mock_jobs


@pytest.mark.asyncio
async def test_unknown_intent(engine, mock_ai_client):
    """
    Scenario: Request unrelated to system capabilities.
    Verifies that the engine handles 'unknown' intents gracefully.
    """
    mock_extraction = ExtractionResult(
        intent="unknown", data={}, is_complete=True, missing_fields=[]
    )

    mock_ai_client.generate_structured_response.return_value = mock_extraction

    response = await engine.process_request("What is the weather?")
    assert response.status == "unknown"
    assert "I'm sorry" in response.message


@pytest.mark.asyncio
async def test_find_similar_jobs_success(
    engine, mock_ai_client, mock_member_repo, mock_job_repo
):
    """
    Scenario: Tailored Job Search.
    Verifies the complex flow: AI Extraction -> Get Profile Context -> Search Jobs by Major.
    """
    mock_extraction = ExtractionResult(
        intent="find similar jobs",
        data={"email": "user@example.com"},
        is_complete=True,
        missing_fields=[],
    )
    mock_user_context = {
        "email": "user@example.com",
        "full_name": "Test User",
        "major": "Computer Science",
        "headline": "Dev",
        "years_experience": 2,
    }
    mock_jobs = [{"job_title": "Software Engineer", "company_name": "TechCo"}]

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.retrieve_context.return_value = mock_user_context
    mock_job_repo.query_listings.return_value = mock_jobs

    response = await engine.process_request("Find me similar jobs")

    assert response.status == "success"
    assert response.data == mock_jobs
    mock_job_repo.query_listings.assert_called_once_with(
        ANY, {"keyword": "Computer Science"}
    )


@pytest.mark.asyncio
async def test_find_similar_colleagues_success(
    engine, mock_ai_client, mock_member_repo
):
    """
    Scenario: Peer Recommendation.
    Verifies the flow: AI Extraction -> Get Profile Context -> Query Similar Members.
    """
    mock_extraction = ExtractionResult(
        intent="find similar colleagues",
        data={"email": "user@example.com"},
        is_complete=True,
        missing_fields=[],
    )
    mock_user_context = {
        "email": "user@example.com",
        "full_name": "Test User",
        "major": "Computer Science",
        "headline": "Dev",
        "years_experience": 2,
    }
    mock_colleagues = [
        {"full_name": "Peer 1", "email": "peer1@ex.com", "major": "Computer Science"}
    ]

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.retrieve_context.return_value = mock_user_context
    mock_member_repo.query_similar.return_value = mock_colleagues

    response = await engine.process_request("Find me some similar colleagues")

    assert response.status == "success"
    assert response.data == mock_colleagues
    mock_member_repo.query_similar.assert_called_once_with(
        ANY, {"major": "Computer Science", "email": "user@example.com"}
    )


@pytest.mark.asyncio
async def test_resume_faq_success(engine, mock_ai_client):
    """
    Scenario: Resume Question success path.
    Verifies that when a PDF is provided and intent is 'resume faq', 
     the multimodal AI response is triggered.
    """
    mock_extraction = ExtractionResult(
        intent="resume faq",
        data={"query": "Does my resume sound professional?"},
        is_complete=True,
        missing_fields=[],
    )
    mock_ai_answer = "Your resume is professional, but consider adding more metrics to your experience section."

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_ai_client.generate_multimodal_response.return_value = mock_ai_answer

    # Simulate PDF upload
    fake_pdf_bytes = b"%PDF-1.4-fake-content"

    response = await engine.process_request(
        "Does my resume sound professional?", file_bytes=fake_pdf_bytes
    )

    assert response.status == "success"
    assert response.data["answer"] == mock_ai_answer
    mock_ai_client.generate_multimodal_response.assert_called_once()


@pytest.mark.asyncio
async def test_resume_faq_missing_file(engine, mock_ai_client):
    """
    Scenario: Resume FAQ missing file.
    Verifies that the engine catches the missing PDF before calling the AI.
    """
    mock_extraction = ExtractionResult(
        intent="resume faq",
        data={"query": "Is my resume good?"},
        is_complete=True,
        missing_fields=[],
    )

    mock_ai_client.generate_structured_response.return_value = mock_extraction

    # Call WITHOUT file_bytes
    response = await engine.process_request("Is my resume good?")

    assert response.status == "incomplete"
    assert "Please upload your resume" in response.message
    assert "resume_pdf" in response.data["missing"]


@pytest.mark.asyncio
async def test_resume_faq_ai_error(engine, mock_ai_client):
    """
    Scenario: AI Model failure during resume analysis.
    Verifies that exceptions in the AI client are caught and returned as errors.
    """
    mock_extraction = ExtractionResult(
        intent="resume faq",
        data={"query": "Analyze this"},
        is_complete=True,
        missing_fields=[],
    )
    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_ai_client.generate_multimodal_response.side_effect = Exception(
        "AI Model Timeout"
    )

    fake_pdf_bytes = b"%PDF-1.4-fake-content"
    response = await engine.process_request("Analyze this", file_bytes=fake_pdf_bytes)

    assert response.status == "error"
    assert "Failed to analyze the resume PDF" in response.message


@pytest.mark.asyncio
async def test_profile_less_job_search(engine, mock_ai_client, mock_member_repo):
    """
    Scenario: Tailored search for unregistered user.
    Should return an empty list instead of crashing when a profile is not found.
    """
    mock_extraction = ExtractionResult(
        intent="find similar jobs",
        data={"email": "ghost@example.com"},
        is_complete=True,
        missing_fields=[],
    )
    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.retrieve_context.return_value = None

    response = await engine.process_request("Find me similar jobs")
    assert response.status == "success"
    assert response.data == []


@pytest.mark.asyncio
async def test_invalid_file_type(engine, mock_ai_client):
    """
    Scenario: Non-PDF file upload.
    Verifies that only PDF files are accepted for multimodal processing.
    """
    mock_extraction = ExtractionResult(
        intent="resume faq",
        data={"query": "Analyze this"},
        is_complete=True,
        missing_fields=[],
    )
    mock_ai_client.generate_structured_response.return_value = mock_extraction

    # Upload as image/jpeg instead of application/pdf
    response = await engine.process_request(
        "Analyze this", file_bytes=b"fake-jpg", mime_type="image/jpeg"
    )

    assert response.status == "incomplete"
    assert response.message == "resume uploaded must be in pdf format"
    assert "valid_pdf" in response.data["missing"]


@pytest.mark.asyncio
async def test_malformed_ai_response(engine, mock_ai_client):
    """
    Scenario: AI returns invalid JSON.
    Verifies that Pydantic validation errors are handled as system errors.
    """
    # Simulate a failure in the AI client's internal validation/parsing
    mock_ai_client.generate_structured_response.side_effect = Exception(
        "ValidationError: missing field 'intent'"
    )

    response = await engine.process_request("Hello")
    assert response.status == "error"
    assert "ValidationError" in response.message


@pytest.mark.asyncio
async def test_empty_search_results(
    engine, mock_ai_client, mock_member_repo, mock_job_repo
):
    """
    Scenario: No results found in database.
    Verifies that empty lists are returned as successful empty results.
    """
    mock_extraction = ExtractionResult(
        intent="find similar jobs",
        data={"email": "user@example.com"},
        is_complete=True,
        missing_fields=[],
    )
    mock_user_context = {
        "email": "user@example.com",
        "major": "Nuclear Physics",
        "headline": "Scientist",
    }

    mock_ai_client.generate_structured_response.return_value = mock_extraction
    mock_member_repo.retrieve_context.return_value = mock_user_context
    mock_job_repo.query_listings.return_value = []  # Empty results

    response = await engine.process_request("Find me similar jobs")
    assert response.status == "success"
    assert response.data == []


@pytest.mark.asyncio
async def test_complex_incomplete_intent(engine, mock_ai_client):
    """
    Scenario: Ambiguous request with multiple missing fields.
    Verifies that the engine correctly identifies and reports all missing data.
    """
    mock_extraction = ExtractionResult(
        intent="register profile",
        data={"full_name": "Test User"},
        is_complete=False,
        missing_fields=["email", "headline", "major", "years_experience"],
    )

    mock_ai_client.generate_structured_response.return_value = mock_extraction

    response = await engine.process_request("Register me")
    assert response.status == "incomplete"
    assert len(response.data["missing"]) == 4
    assert "email" in response.data["missing"]


def test_ai_client_api_key_sanitization():
    """
    Verify that AIClient cleans API keys of common copy-paste artifacts 
    (quotes, smart quotes, whitespace).
    """
    test_keys = [
        ('"AIza-123"', "AIza-123"),
        ("'AIza-123'", "AIza-123"),
        ("\u201cAIza-123\u201d", "AIza-123"),
        ("\u2018AIza-123\u2019", "AIza-123"),
        ("  AIza-123  ", "AIza-123"),
        ("\u201c AIza-123 \u201d", "AIza-123"),
    ]

    for input_key, expected_key in test_keys:
        client = AIClient(api_key=input_key)
        assert client._api_key == expected_key, f"Failed to sanitize key: {input_key} "


def test_ai_client_no_api_key():
    """
    Verify that AIClient raises a ValueError when no key is provided 
    and no environment variable is set.
    """
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GEMINI_API_KEY is not set"):
            AIClient(api_key=None)
