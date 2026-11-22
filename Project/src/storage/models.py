"""
Storage Models Module
=====================

This module defines the Pydantic schemas used at the storage boundary. 
While SQLAlchemy models handle the database structure, these schemas 
ensure that data returned to the Engine or Interface layers is 
validated, typed, and sanitized.

Design Choice:
Using `ConfigDict(from_attributes=True)` allows Pydantic to seamlessly 
convert SQLAlchemy ORM objects into these schemas using 
`model_validate(orm_object)`.
"""
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional


class MemberSchema(BaseModel):
    """
    Pydantic schema for a member's professional profile.
    
    Used for data validation and serialization when retrieving 
    profiles from the member database.
    """

    id: Optional[int] = None
    full_name: str
    email: EmailStr
    headline: str
    major: str
    years_experience: int

    # Allow conversion from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)


class JobSchema(BaseModel):
    """
    Pydantic schema for a job listing.
    
    Used for data validation and serialization when retrieving 
    listings from the jobs database.
    """

    id: Optional[int] = None
    job_title: str
    company_name: str
    location: str
    job_summary: str
    application_link: str

    # Allow conversion from SQLAlchemy ORM objects
    model_config = ConfigDict(from_attributes=True)
