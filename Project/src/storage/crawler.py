"""
Job Crawler Module
==================

This module implements the autonomous data acquisition system for Career Kick. 
It is responsible for fetching real-world job listings from external APIs 
and ensuring they are persisted in the internal job database.

Components:
1. AdzunaClient: A specialized HTTP client for the Adzuna Job API.
2. JobWebCrawler: The orchestrator that manages keywords, fetches data, 
   and delegates persistence to the JobRepository.
3. run_continuous_crawler: An asynchronous background loop that keeps 
   the job database fresh.

Design Goal:
The crawler is decoupled from the API and Database logic, allowing for 
easy swaps of job data sources (e.g., moving from Adzuna to LinkedIn) 
without affecting the rest of the system.
"""
import asyncio
import logging
import os
import httpx
from typing import List, Dict, Any, Optional
from src.storage.repositories import JobRepository
from src.storage.database import JobsSessionLocal
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AdzunaClient:
    """
    Client dedicated to communicating with the Adzuna Job API.
    
    Decouples raw HTTP communication and API-specific field mapping 
    from the higher-level crawling orchestration.
    """

    def __init__(
        self, app_id: Optional[str], app_key: Optional[str], country: str = "us"
    ):
        """
        Initializes the Adzuna API client.

        Args:
            app_id (Optional[str]): The application ID provided by Adzuna.
            app_key (Optional[str]): The application key provided by Adzuna.
            country (str): The country code for job search (defaults to "us").
        """
        self.app_id = app_id
        self.app_key = app_key
        self.country = country
        self.base_url = f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/1"

    async def fetch_jobs(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Fetches raw job data from the Adzuna API based on a search keyword.

        This method handles the HTTP request and transforms the Adzuna-specific 
        JSON response into a standardized internal dictionary format that 
        matches the JobSchema.

        Args:
            keyword (str): The professional skill or role to search for.

        Returns:
            List[Dict[str, Any]]: A list of normalized job dictionaries.

        Raises:
            ValueError: If API credentials are not provided.
            httpx.HTTPStatusError: If the API request fails.
        """
        if not self.app_id or not self.app_key:
            raise ValueError("Adzuna API credentials missing")

        params: Dict[str, Any] = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": 20,
            "what": keyword,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            # Map Adzuna's complex nested response to our flat internal JobSchema
            return [
                {
                    "job_title": job.get("title", "N/A"),
                    "company_name": job.get("company", {}).get(
                        "display_name", "Unknown Company"
                    ),
                    "location": job.get("location", {}).get(
                        "display_name", "Remote/Unknown"
                    ),
                    "job_summary": job.get("description", "No description available."),
                    "application_link": job.get("redirect_url", "#"),
                }
                for job in data.get("results", [])
            ]


class JobWebCrawler:
    """
    Orchestrator for job discovery.
    
    Coordinates the process of identifying target keywords, fetching 
    data via the AdzunaClient, and persisting that data via the JobRepository.
    """

    def __init__(self, job_repo: JobRepository):
        """
        Initializes the crawler with its required storage repository.

        Args:
            job_repo (JobRepository): The repository used to save found jobs.
        """
        self.job_repo = job_repo
        # Initialize the specialized API client using environment variables
        self.api_client = AdzunaClient(
            app_id=os.getenv("ADZUNA_APP_ID"), app_key=os.getenv("ADZUNA_APP_KEY")
        )

    async def crawl_and_persist_jobs(self) -> Dict[str, int]:
        """
        Main execution loop: fetches data for a set of keywords and saves them.

        This method iterates through a predefined list of high-demand 
        professional roles to ensure the database has a diverse set 
        of opportunities for users.

        Returns:
            Dict[str, int]: Statistics on the crawl (added, exists, failed).
        """
        stats = {"added": 0, "exists": 0, "failed": 0}
        keywords = [
            "Software Engineer",
            "Data Analyst",
            "Project Manager",
            "Marketing Specialist",
        ]

        async with JobsSessionLocal() as session:
            for keyword in keywords:
                try:
                    # Fetch raw listings from the external API
                    listings = await self.api_client.fetch_jobs(keyword)

                    for job_dict in listings:
                        # Delegate the duplicate check and insertion to the repository
                        status_code = await self.job_repo.store_job(session, job_dict)
                        if status_code == "External job data successfully added":
                            stats["added"] += 1
                        elif status_code == "job already exists":
                            stats["exists"] += 1
                        else:
                            stats["failed"] += 1
                except Exception as e:
                    logger.error(f"Failed to process listings for {keyword}: {e}")

        return stats


async def run_continuous_crawler(job_repo: JobRepository):
    """
    Autonomous background loop for periodic data refreshing.
    
    This function is intended to be run as a background task (via asyncio.create_task) 
    upon application startup. It ensures that the job database is updated 
    hourly without requiring manual triggers.

    Args:
        job_repo (JobRepository): The repository used for job persistence.
    """
    logger.info("Starting autonomous continuous job crawler loop...")
    crawler = JobWebCrawler(job_repo=job_repo)

    while True:
        try:
            stats = await crawler.crawl_and_persist_jobs()
            logger.info(f"Continuous Crawl Cycle Complete: {stats}")
        except Exception as e:
            logger.error(f"Critical error in crawler loop: {e}")
        
        # Wait for one hour before the next cycle to respect API rate limits
        await asyncio.sleep(3600) 
