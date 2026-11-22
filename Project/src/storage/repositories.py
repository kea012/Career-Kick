"""
Storage Repositories Module
===========================

This module implements the Repository Pattern to decouple the 
CareerEngine from the underlying data access technology (SQLAlchemy).

Key Responsibilities:
1. Data Persistence: Handling the insertion and updates of profiles and jobs.
2. Complex Querying: Implementing search logic (e.g., keyword search with 
   basic stemming and case-insensitivity).
3. File Management: Managing the physical storage of PDF resumes on disk.

By abstracting the database calls into these repositories, the Engine 
remains focused on orchestration and AI logic, making the system 
easier to test and maintain.
"""
import logging
import os
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select, Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.database import Base
from src.storage.models import MemberSchema, JobSchema

logger = logging.getLogger(__name__)

# Define the local directory where PDF resumes are stored.
RESUME_STORAGE_DIR = "/tmp/career_kick/resumes"
os.makedirs(RESUME_STORAGE_DIR, exist_ok=True)


# --- SQLAlchemy ORM Models ---
# These classes define the actual database table structures.

class Member(Base):
    """SQLAlchemy model for the 'members' table."""
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    headline = Column(String, nullable=False)
    major = Column(String, nullable=False)
    years_experience = Column(Integer, nullable=False)


class Job(Base):
    """SQLAlchemy model for the 'jobs' table."""
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    job_summary = Column(String, nullable=False)
    application_link = Column(String, unique=True, nullable=False)


# --- Repositories ---

class MemberRepository:
    """
    Handles all persistence and retrieval logic for professional profiles.
    """

    async def store_profile(self, session: AsyncSession, profile_data: dict) -> str:
        """
        Validates and persists a new professional profile.

        Args:
            session (AsyncSession): The database session to use.
            profile_data (dict): The profile fields extracted by the AI.

        Returns:
            str: A status message ('Profile active', 'Already registered', 
                 or 'Incomplete submission').
        """
        # 1. Basic Validation: Ensure all required fields are present
        required_keys = ["full_name", "email", "headline", "major", "years_experience"]
        for key in required_keys:
            if key not in profile_data or profile_data[key] is None:
                return "Incomplete submission"

        # 2. Uniqueness Check: Prevent duplicate email registrations
        email = profile_data["email"]
        stmt = select(Member).where(Member.email == email)
        result = await session.execute(stmt)
        if result.scalars().first():
            return "Already registered"

        # 3. Persistence
        try:
            new_member = Member(**profile_data)
            session.add(new_member)
            await session.commit()
            return "Profile active"
        except Exception as e:
            logger.error(f"Database error storing profile: {e}")
            await session.rollback()
            return "Incomplete submission"

    async def get_all_profiles(self, session: AsyncSession) -> List[MemberSchema]:
        """Retrieves all registered members and converts them to MemberSchema."""
        stmt = select(Member)
        result = await session.execute(stmt)
        return [MemberSchema.model_validate(m) for m in result.scalars().all()]

    async def retrieve_context(
        self, session: AsyncSession, email: str
    ) -> Optional[MemberSchema]:
        """Fetches a specific member's profile by email for similarity matching."""
        stmt = select(Member).where(Member.email == email)
        result = await session.execute(stmt)
        member = result.scalars().first()
        return MemberSchema.model_validate(member) if member else None

    async def query_similar(
        self, session: AsyncSession, criteria: Dict[str, Any]
    ) -> List[MemberSchema]:
        """
        Finds other members based on similarity criteria (e.g., same major).
        
        Ensures the requesting user is excluded from their own recommendations.
        """
        stmt = select(Member)
        if "major" in criteria and criteria["major"]:
            stmt = stmt.where(Member.major == criteria["major"])
        if "email" in criteria:
            stmt = stmt.where(Member.email != criteria["email"])
        result = await session.execute(stmt)
        return [MemberSchema.model_validate(m) for m in result.scalars().all()]

    async def search_members(
        self, session: AsyncSession, keyword: str
    ) -> List[MemberSchema]:
        """
        Search for members by name, major, or professional headline.
        
        Implementation Detail:
        - Splits the keyword into individual terms.
        - Performs basic stemming by removing trailing 's'.
        - Requires that EVERY term provided is present in at least one 
          of the searchable fields (AND logic).
        """
        if not keyword:
            return []

        # Basic stemming: 'developers' -> 'developer'
        terms = [term.strip().rstrip("s") for term in keyword.split() if term.strip()]

        stmt = select(Member)
        for term in terms:
            search_term = f"%{term}%"
            # Case-insensitive partial match across multiple columns
            stmt = stmt.where(
                (Member.full_name.ilike(search_term))
                | (Member.major.ilike(search_term))
                | (Member.headline.ilike(search_term))
            )

        result = await session.execute(stmt)
        return [MemberSchema.model_validate(m) for m in result.scalars().all()]

    async def delete(self, session: AsyncSession, email: str) -> str:
        """Removes a user profile from the database by email."""
        stmt = select(Member).where(Member.email == email)
        result = await session.execute(stmt)
        member = result.scalars().first()
        if not member:
            return "Profile not found"
        await session.delete(member)
        await session.commit()
        return "Profile successfully deleted"


class JobRepository:
    """
    Handles all persistence and retrieval logic for job listings.
    """

    async def get_all_jobs(self, session: AsyncSession) -> List[JobSchema]:
        """Retrieves all jobs from the database and converts them to JobSchema."""
        stmt = select(Job)
        result = await session.execute(stmt)
        return [JobSchema.model_validate(j) for j in result.scalars().all()]

    async def query_listings(
        self, session: AsyncSession, criteria: Dict[str, Any]
    ) -> List[JobSchema]:
        """
        Search for jobs based on a keyword.
        
        Matches the keyword against both the job title and the 
        detailed job summary.
        """
        stmt = select(Job)
        if "keyword" in criteria and criteria["keyword"]:
            keyword = f"%{criteria['keyword']}%"
            stmt = stmt.where(
                (Job.job_summary.ilike(keyword)) | (Job.job_title.ilike(keyword))
            )
        result = await session.execute(stmt)
        return [JobSchema.model_validate(j) for j in result.scalars().all()]

    async def store_job(self, session: AsyncSession, job_data: dict) -> str:
        """
        Persists a job listing found by the crawler.
        
        Ensures that duplicate listings (based on application link) 
        are not added to the database.
        """
        required_keys = [
            "job_title",
            "company_name",
            "location",
            "job_summary",
            "application_link",
        ]
        for key in required_keys:
            if key not in job_data or job_data[key] is None:
                return "External job data failed to be added"

        link = job_data["application_link"]
        stmt = select(Job).where(Job.application_link == link)
        result = await session.execute(stmt)
        if result.scalars().first():
            return "Job already exists"

        try:
            new_job = Job(**job_data)
            session.add(new_job)
            await session.commit()
            return "External job data successfully added"
        except Exception as e:
            logger.error(f"Error persisting job: {e}")
            await session.rollback()
            return "External job data failed to be added"

    async def delete(self, session: AsyncSession, link: str) -> str:
        """Removes a job listing using its unique application link."""
        stmt = select(Job).where(Job.application_link == link)
        result = await session.execute(stmt)
        job = result.scalars().first()
        if not job:
            return "Job not found"
        await session.delete(job)
        await session.commit()
        return "Job successfully deleted"


class ResumeRepository:
    """
    Handles physical persistence of uploaded resume PDF files.
    
    Unlike members and jobs, resumes are stored as files on the 
    filesystem for efficiency and ease of multimodal AI processing.
    """

    def save_resume(self, file_bytes: bytes) -> str:
        """
        Saves raw PDF bytes to disk with a unique UUID filename.

        Returns:
            str: The unique resume_id used to retrieve the file later.
        """
        resume_id = str(uuid.uuid4())
        file_path = os.path.join(RESUME_STORAGE_DIR, f"{resume_id}.pdf")
        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            return resume_id
        except Exception as e:
            logger.error(f"Error saving resume file: {e}")
            raise e

    def get_resume(self, resume_id: str) -> Optional[bytes]:
        """
        Retrieves the raw bytes of a resume from disk.

        Returns:
            Optional[bytes]: The file content, or None if the file doesn't exist.
        """
        file_path = os.path.join(RESUME_STORAGE_DIR, f"{resume_id}.pdf")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading resume file {resume_id}: {e}")
            return None
