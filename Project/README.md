# Project Name: Career Kick AI Assistant

## Description
- Career Kick AI Assistant is a chatbot that can help refine resumes through its feedback, provide career advice, connect professionals with others, and allow users to find currently open job applications. Although a person is not required to sign up to use these features, the incentive for signing up is the ability for other professionals in related fields to look through a list of similar professionals and build a community with those they can relate to. 

## Source Code Directory
- CAREER_KICK/src

## Test Code Directory
- CAREER_KICK/tests

## Requirement Specification Path
- CAREER_KICK/requirements.txt

## Design Document Path
- CAREER_KICK/FUNCTIONALITY.md
- CAREER_KICK/CONTRACT.md

## Link to the demo video 
https://youtu.be/w_UXpV515eA

## Setup and execution instructions

### 1. Prerequisites
- Python 3.13+
- PostgreSQL database instance

### 2. Environment Configuration
Create a `.env` file in the root directory with the following variables:
```env
# Gemini AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here
MODEL_NAME=gemma-4-31b-it

# Adzuna Job API Configuration
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key

# Database Configuration
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/career_kick_users
JOBS_DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/career_kick_jobs
```

### 3. Installation
```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Database Setup
Ensure you have created the two required PostgreSQL databases: `career_kick_users` and `career_kick_jobs`. The application will automatically create the necessary tables on first run or during test execution.

### 5. Execution
To start the FastAPI server:
```bash
python -m src.interface.api
```
The server will start at `http://localhost:8000`. You can access the frontend UI at:
`http://localhost:8000/static/index.html`

### 6. Running Tests
The project uses `pytest` for tests.
```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/engine       # Unit tests for the orchestration engine
pytest tests/interface    # API endpoint tests
pytest tests/storage      # Database integration tests
```