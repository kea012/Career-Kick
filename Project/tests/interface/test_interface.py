"""
Interface API Tests
====================

These tests verify the FastAPI endpoints of the Career Kick application. 
To avoid dependency on actual AI models and databases, the `CareerEngine` 
is mocked.

Test Coverage:
1. Health Check: Verifies the /health endpoint.
2. Chat Interaction: Validates success and 'incomplete' responses.
3. File Validation: Ensures non-PDF uploads are rejected by the API.
4. PDF Integration: Verifies that PDF uploads are correctly handled and passed to the engine.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from src.interface.api import app

client = TestClient(app)


@pytest.fixture
def mock_engine():
    """
    Mocks the CareerEngine to avoid actual AI and DB calls during API tests.
    We patch the 'engine' instance inside the api module.
    """
    with pytest.MonkeyPatch().context() as mp:
        mock = AsyncMock()
        # We must patch the engine instance that was already initialized in api.py
        import src.interface.api as api

        mp.setattr(api, "engine", mock)
        yield mock


def test_health_check():
    """Verify the health check endpoint is working."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_chat_success(mock_engine):
    """
    Scenario: Successful chat interaction.
    Verifies that a valid message is processed and a success response is returned.
    """
    # Mock the engine's return value (EngineResponse)
    mock_engine.process_request.return_value = MagicMock(
        model_dump=lambda: {"status": "success", "message": "Hello!", "data": None}
    )

    response = client.post("/chat", data={"message": "Hello"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["message"] == "Hello!"


@pytest.mark.asyncio
async def test_chat_incomplete(mock_engine):
    """
    Scenario: Request missing information.
    Verifies that the API correctly forwards 'incomplete' status and missing fields.
    """
    mock_engine.process_request.return_value = MagicMock(
        model_dump=lambda: {
            "status": "incomplete",
            "message": "Missing email",
            "data": {"missing": ["email"]},
        }
    )

    response = client.post("/chat", data={"message": "Register me"})
    assert response.status_code == 200
    assert response.json()["status"] == "incomplete"
    assert "email" in response.json()["data"]["missing"]


@pytest.mark.asyncio
async def test_chat_invalid_file_type():
    """
    Scenario: Non-PDF file upload.
    Verifies that the API rejects non-PDF files before they even reach the engine.
    """
    # We don't need to mock the engine here because the API should reject it first
    file_content = b"fake text content"
    files = {"file": ("test.txt", file_content, "text/plain")}

    response = client.post("/chat", data={"message": "Analyze this"}, files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "incomplete"
    assert "pdf format" in response.json()["message"]


@pytest.mark.asyncio
async def test_chat_pdf_upload(mock_engine):
    """
    Scenario: Successful PDF upload and processing.
    Verifies that PDF bytes are correctly accepted and passed to the engine.
    """
    mock_engine.process_request.return_value = MagicMock(
        model_dump=lambda: {
            "status": "success",
            "message": "PDF analyzed",
            "data": {"answer": "Looks good!"},
        }
    )

    file_content = b"%PDF-1.4-fake-content"
    files = {"file": ("resume.pdf", file_content, "application/pdf")}

    response = client.post("/chat", data={"message": "Analyze my resume"}, files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["answer"] == "Looks good!"
