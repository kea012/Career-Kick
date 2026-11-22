"""
Interface API Module
====================

This module implements the FastAPI web server that serves as the primary 
entry point for the Career Kick application. It handles HTTP requests from the 
frontend, manages file uploads (PDF resumes), and interacts with the `CareerEngine` 
to process user queries.

Key Features:
1. REST API: Provides endpoints for chatting (/chat) and system health (/health).
2. File Handling: Integrates with `ResumeRepository` to save and retrieve PDF resumes.
3. Background Tasks: Launches an autonomous job crawler on startup via the 
   FastAPI lifespan event.
4. Static Hosting: Serves the frontend HTML/JS from the /static directory.
"""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from typing import Optional  # noqa: E402
import uvicorn  # noqa: E402
import logging  # noqa: E402
import asyncio  # noqa: E402

from src.engine.engine import CareerEngine  # noqa: E402
from src.engine.ai_client import AIClient  # noqa: E402
from src.storage.repositories import MemberRepository, JobRepository, ResumeRepository  # noqa: E402
from src.storage.crawler import run_continuous_crawler  # noqa: E402

# Setup logging to track API requests and background crawler status
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Dependency Injection ---
# Initialize the core components. These are shared across all API requests.
ai_client = AIClient()
member_repo = MemberRepository()
job_repo = JobRepository()
resume_repo = ResumeRepository()
engine = CareerEngine(ai_client, member_repo, job_repo)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    
    Startup:
    - Launches the 'run_continuous_crawler' background task, which periodically 
      fetches new job listings from external APIs and persists them to the database.
      
    Shutdown:
    - Gracefully cancels the crawler task to ensure a clean exit.
    """
    logger.info("Application starting up...")
    # Launch the continuous crawler as a background task to avoid blocking the API
    crawler_task = asyncio.create_task(run_continuous_crawler(job_repo))
    logger.info("Job crawler task scheduled in background.")

    yield

    logger.info("Application shutting down...")
    crawler_task.cancel()
    try:
        await crawler_task
    except asyncio.CancelledError:
        logger.info("Job crawler task cancelled successfully.")


app = FastAPI(title="Career Kick API", lifespan=lifespan)

# Enable CORS (Cross-Origin Resource Sharing) to allow the frontend 
# (potentially running on a different port/domain) to communicate with this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
async def chat(
    message: str = Form(...),
    file: Optional[UploadFile] = File(None),
    resume_id: Optional[str] = Form(None),
):
    """
    The primary endpoint for the Career Kick chatbox.
    
    This endpoint handles a multi-part form submission containing:
    - message: The user's natural language query.
    - file: An optional PDF resume upload.
    - resume_id: An optional ID referring to a previously uploaded resume.

    Workflow:
    1. If a new file is uploaded, validate it is a PDF, save it via `ResumeRepository`, 
       and generate a `resume_id`.
    2. If a `resume_id` is provided without a new file, retrieve the existing bytes from storage.
    3. Pass the query and the resume bytes (if any) to the `CareerEngine` for processing.
    4. Return the engine's response along with the current `resume_id` so the 
       frontend can maintain the session context.

    Returns:
        A JSON response containing the status, message, and optional data payload.
    """
    try:
        file_bytes = None
        mime_type = "application/pdf"
        current_resume_id = resume_id

        # 1. Handle new file upload
        if file:
            if file.content_type != "application/pdf":
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "incomplete",
                        "message": "resume uploaded must be in pdf format",
                        "data": {"missing": ["valid_pdf"]},
                    },
                )
            file_bytes = await file.read()
            mime_type = file.content_type

            # Save file to storage and get a unique ID for future reference
            current_resume_id = resume_repo.save_resume(file_bytes)

        # 2. Handle existing resume via resume_id (Context Persistence)
        elif resume_id:
            file_bytes = resume_repo.get_resume(resume_id)
            if not file_bytes:
                # If the file was deleted from disk, reset the ID
                current_resume_id = None

        # 3. Core Processing: Delegate the request to the Engine
        response = await engine.process_request(
            user_input=message, file_bytes=file_bytes, mime_type=mime_type
        )

        # Return the response along with the resume_id so the frontend can track it
        result_dict = response.model_dump()
        result_dict["resume_id"] = current_resume_id
        return result_dict

    except Exception as e:
        logger.exception(f"API Error: {e}")
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@app.get("/health")
async def health_check():
    """Simple health check endpoint to verify the API is running."""
    return {"status": "healthy"}


# Mount the static files directory to serve the HTML/JS frontend.
# This allows users to access the UI via http://localhost:8000/static/index.html
app.mount("/static", StaticFiles(directory="src/interface/static"), name="static")

if __name__ == "__main__":
    # Run the server using uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
