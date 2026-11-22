"""
Storage Integration Tests
=========================

These tests verify that the Repository layer correctly interacts with 
a real PostgreSQL database. Unlike unit tests, these ensure that 
SQLAlchemy queries, database constraints, and transaction logic 
work as expected.

Test Coverage:
1. Member Repository: 
   - Successful profile storage.
   - Duplicate email prevention.
   - Incomplete submission handling.
   - Profile retrieval and deletion.
   - Complex keyword search (stemming, case-insensitivity, multi-word).
2. Job Repository:
   - Successful job insertion.
   - Duplicate link prevention.
   - Job retrieval and keyword-based filtering.
   - Job deletion.
"""
import pytest
import pytest_asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.storage.database import Base
from src.storage.repositories import MemberRepository, JobRepository, Job

# Database configuration for integration tests.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://kennethea:postgres@localhost:5432/career_kick_users",
)


@pytest_asyncio.fixture
async def db_session():
    """
    Database Session Fixture: Provides an isolated, asynchronous DB session.
    
    Before each test, it:
    1. Creates the schema based on the Base metadata.
    2. Truncates existing data to ensure a clean state.
    """
    from sqlalchemy import text

    engine = create_async_engine(DATABASE_URL)

    # Ensure schema is created and table is empty before starting tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE members"))
        await conn.execute(text("TRUNCATE TABLE jobs"))

    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_store_profile_success(db_session):
    """
    Scenario: Successful Registration.
    Verifies that when a user submits all required fields with a unique email,
    the system stores the record and returns 'Profile active'.
    """
    profile_data = {
        "full_name": "Alice Smith",
        "email": "alice.smith@example.com",
        "headline": "Full Stack Developer",
        "major": "Computer Science",
        "years_experience": 3,
    }
    repo = MemberRepository()
    result = await repo.store_profile(db_session, profile_data)
    assert result == "Profile active"


@pytest.mark.asyncio
async def test_store_profile_already_registered(db_session):
    """
    Scenario: Duplicate Email Registration.
    Verifies that the system detects an existing email in the database
    and returns 'Already registered'.
    """
    email = "duplicate@example.com"
    existing_profile = {
        "full_name": "Existing User",
        "email": email,
        "headline": "Software Engineer",
        "major": "Information Technology",
        "years_experience": 2,
    }
    repo = MemberRepository()
    await repo.store_profile(db_session, existing_profile)

    new_profile = {
        "full_name": "New User",
        "email": email,
        "headline": "Product Manager",
        "major": "Business Admin",
        "years_experience": 5,
    }
    result = await repo.store_profile(db_session, new_profile)
    assert result == "Already registered"


@pytest.mark.asyncio
async def test_store_profile_incomplete_submission(db_session):
    """
    Scenario: Incomplete Form Submission.
    Verifies that the system identifies missing mandatory fields and returns 'Incomplete submission'.
    """
    incomplete_profile = {
        "full_name": "Bob Jones",
        "headline": "Data Scientist",
        "major": "Statistics",
        "years_experience": 4,
    }
    repo = MemberRepository()
    result = await repo.store_profile(db_session, incomplete_profile)
    assert result == "Incomplete submission"


@pytest.mark.asyncio
async def test_store_external_job_success(db_session):
    """
    Scenario: External job data successfully added.
    Verifies that a valid job listing is correctly persisted to the database.
    """
    job_data = {
        "job_title": "Software Engineer",
        "company_name": "TechCorp",
        "location": "San Francisco, CA",
        "job_summary": "Develop modern high-performance cloud applications.",
        "application_link": "https://techcorp.jobs/se-101",
    }
    repo = JobRepository()
    result = await repo.store_job(db_session, job_data)
    assert result == "External job data successfully added"

    from sqlalchemy import select

    stmt = select(Job).where(Job.application_link == "https://techcorp.jobs/se-101")
    db_result = await db_session.execute(stmt)
    job_record = db_result.scalars().first()
    assert job_record is not None
    assert job_record.job_title == "Software Engineer"


@pytest.mark.asyncio
async def test_store_external_job_failed_to_be_added(db_session):
    """
    Scenario: External job data failed to be added due to missing field.
    """
    incomplete_job = {
        "company_name": "TechCorp",
        "location": "San Francisco, CA",
        "job_summary": "Develop modern high-performance cloud applications.",
        "application_link": "https://techcorp.jobs/se-101",
    }
    repo = JobRepository()
    result = await repo.store_job(db_session, incomplete_job)
    assert result == "External job data failed to be added"


@pytest.mark.asyncio
async def test_store_external_job_already_exists(db_session):
    """
    Scenario: Job already exists due to duplicate application link.
    Verifies that the system prevents duplicate listings based on the URL.
    """
    link = "https://techcorp.jobs/duplicate-link"
    job_data_1 = {
        "job_title": "Frontend Engineer",
        "company_name": "WebInc",
        "location": "Remote",
        "job_summary": "Build beautiful web experiences.",
        "application_link": link,
    }
    repo = JobRepository()
    await repo.store_job(db_session, job_data_1)

    job_data_2 = {
        "job_title": "Backend Engineer",
        "company_name": "API Corp",
        "location": "Austin, TX",
        "job_summary": "Scale the core API endpoints.",
        "application_link": link,
    }
    result = await repo.store_job(db_session, job_data_2)
    assert result == "Job already exists"


@pytest.mark.asyncio
async def test_get_profiles_success(db_session):
    """
    Scenario: Successful Profile Retrieval.
    Verifies that all stored profiles can be retrieved and converted to schemas.
    """
    profiles = [
        {
            "full_name": "User One",
            "email": "user1@example.com",
            "headline": "Role One",
            "major": "Major One",
            "years_experience": 1,
        },
        {
            "full_name": "User Two",
            "email": "user2@example.com",
            "headline": "Role Two",
            "major": "Major Two",
            "years_experience": 2,
        },
    ]
    repo = MemberRepository()
    for p in profiles:
        await repo.store_profile(db_session, p)

    result = await repo.get_all_profiles(db_session)
    assert len(result) == 2
    emails = [p.email for p in result]
    assert "user1@example.com" in emails


@pytest.mark.asyncio
async def test_delete_profile_success(db_session):
    """
    Scenario: Successful Profile Deletion.
    """
    email = "delete-me@example.com"
    profile_data = {
        "full_name": "Disposable User",
        "email": email,
        "headline": "Temporary Role",
        "major": "General Studies",
        "years_experience": 0,
    }
    repo = MemberRepository()
    await repo.store_profile(db_session, profile_data)
    result = await repo.delete(db_session, email)
    assert result == "Profile successfully deleted"


@pytest.mark.asyncio
async def test_delete_profile_not_found(db_session):
    """
    Scenario: Attempt to delete a non-existent profile.
    """
    repo = MemberRepository()
    result = await repo.delete(db_session, "ghost@example.com")
    assert result == "Profile not found"


@pytest.mark.asyncio
async def test_get_jobs_success(db_session):
    """
    Scenario: Successful Job Retrieval.
    """
    jobs_data = [
        {
            "job_title": "SRE",
            "company_name": "CloudX",
            "location": "Seattle",
            "job_summary": "Scale systems.",
            "application_link": "https://cloudx.com/sre",
        },
        {
            "job_title": "DevOps",
            "company_name": "DevOpsInc",
            "location": "Remote",
            "job_summary": "CI/CD pipelines.",
            "application_link": "https://devopsinc.com/devops",
        },
    ]
    repo = JobRepository()
    for j in jobs_data:
        await repo.store_job(db_session, j)

    result = await repo.get_all_jobs(db_session)
    assert len(result) == 2
    links = [j.application_link for j in result]
    assert "https://cloudx.com/sre" in links


@pytest.mark.asyncio
async def test_delete_job_success(db_session):
    """
    Scenario: Successful Job Deletion.
    """
    link = "https://techcorp.jobs/delete-me"
    job_data = {
        "job_title": "Frontend Dev",
        "company_name": "TechCorp",
        "location": "Austin",
        "job_summary": "React expert.",
        "application_link": link,
    }
    repo = JobRepository()
    await repo.store_job(db_session, job_data)
    result = await repo.delete(db_session, link)
    assert result == "Job successfully deleted"


@pytest.mark.asyncio
async def test_search_members_by_name(db_session):
    """Scenario: Search members by name."""
    profile = {
        "full_name": "Alice Smith",
        "email": "alice@example.com",
        "headline": "Dev",
        "major": "CS",
        "years_experience": 1,
    }
    repo = MemberRepository()
    await repo.store_profile(db_session, profile)

    result = await repo.search_members(db_session, "Alice")
    assert len(result) == 1
    assert result[0].full_name == "Alice Smith"


@pytest.mark.asyncio
async def test_search_members_by_major(db_session):
    """Scenario: Search members by major."""
    profile = {
        "full_name": "Bob",
        "email": "bob@example.com",
        "headline": "Dev",
        "major": "Computer Science",
        "years_experience": 1,
    }
    repo = MemberRepository()
    await repo.store_profile(db_session, profile)

    result = await repo.search_members(db_session, "Computer Science")
    assert len(result) == 1
    assert result[0].major == "Computer Science"


@pytest.mark.asyncio
async def test_search_members_by_headline(db_session):
    """Scenario: Search members by professional headline."""
    profile = {
        "full_name": "Charlie",
        "email": "charlie@example.com",
        "headline": "Senior Software Engineer",
        "major": "Math",
        "years_experience": 1,
    }
    repo = MemberRepository()
    await repo.store_profile(db_session, profile)

    result = await repo.search_members(db_session, "Software Engineer")
    assert len(result) == 1
    assert "Software Engineer" in result[0].headline


@pytest.mark.asyncio
async def test_search_members_multi_word_and_plurals(db_session):
    """
    Scenario: Search using multi-word keywords and plurals.
    Verifies that 'software engineers' matches 'Software Engineer' or 'Software Engineering'.
    """
    profiles = [
        {
            "full_name": "User 1",
            "email": "u1@ex.com",
            "headline": "Software Engineer",
            "major": "CS",
            "years_experience": 1,
        },
        {
            "full_name": "User 2",
            "email": "u2@ex.com",
            "headline": "Web Developer",
            "major": "Software Engineering",
            "years_experience": 1,
        },
        {
            "full_name": "User 3",
            "email": "u3@ex.com",
            "headline": "Designer",
            "major": "Art",
            "years_experience": 1,
        },
    ]
    repo = MemberRepository()
    for p in profiles:
        await repo.store_profile(db_session, p)

    # Search for 'software engineers' (plural)
    # Should match User 1 (headline) and User 2 (major)
    result = await repo.search_members(db_session, "software engineers")
    assert len(result) == 2

    # Search for 'developers' (plural)
    # Should match User 2 (headline)
    result_devs = await repo.search_members(db_session, "developers")
    assert len(result_devs) == 1
    assert "Developer" in result_devs[0].headline


@pytest.mark.asyncio
async def test_search_members_case_insensitive(db_session):
    """Scenario: Search is case-insensitive."""
    profile = {
        "full_name": "Alice Smith",
        "email": "alice@example.com",
        "headline": "Frontend Developer",
        "major": "CS",
        "years_experience": 1,
    }
    repo = MemberRepository()
    await repo.store_profile(db_session, profile)

    result = await repo.search_members(db_session, "FRONTEND")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_search_members_no_results(db_session):
    """Scenario: Search returns empty list when no match is found."""
    repo = MemberRepository()
    result = await repo.search_members(db_session, "NonExistentSkill")
    assert result == []


@pytest.mark.asyncio
async def test_query_jobs_by_title(db_session):
    """Scenario: Query jobs by keyword in title."""
    job_data = {
        "job_title": "Python Developer",
        "company_name": "PyCorp",
        "location": "Remote",
        "job_summary": "Write python code.",
        "application_link": "https://pycorp.com/1",
    }
    repo = JobRepository()
    await repo.store_job(db_session, job_data)

    result = await repo.query_listings(db_session, {"keyword": "Python"})
    assert len(result) == 1
    assert "Python" in result[0].job_title


@pytest.mark.asyncio
async def test_query_jobs_by_summary(db_session):
    """Scenario: Query jobs by keyword in summary."""
    job_data = {
        "job_title": "Engineer",
        "company_name": "Tech",
        "location": "NY",
        "job_summary": "Experience with Kubernetes and AWS.",
        "application_link": "https://tech.com/1",
    }
    repo = JobRepository()
    await repo.store_job(db_session, job_data)

    result = await repo.query_listings(db_session, {"keyword": "Kubernetes"})
    assert len(result) == 1
    assert "Kubernetes" in result[0].job_summary


@pytest.mark.asyncio
async def test_query_jobs_no_results(db_session):
    """Scenario: Query jobs returns empty list when no match is found."""
    repo = JobRepository()
    result = await repo.query_listings(db_session, {"keyword": "Unicorn"})
    assert result == []
