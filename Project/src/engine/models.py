"""
Engine Models Module
====================

This module defines the strongly-typed data structures used by the `CareerEngine`. 
By using Pydantic models, we ensure that the data flowing from the AI's 
unstructured JSON response is validated and consistent before it reaches the 
business logic or storage layers.

These models act as the 'Schema' for the interface contracts defined in CONTRACT.md.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """
    Strongly typed representation of a user's professional profile.
    
    This model is used to pass validated profile data from the AI extraction 
    phase to the MemberRepository for storage.
    """

    full_name: str
    email: str
    headline: str
    major: str
    years_experience: int


class ExtractionResult(BaseModel):
    """
    The unified result of the AI extraction and reflection process.
    
    This model represents the AI's understanding of the user's request. 
    It combines the identified intent, the extracted entities, and a 
    self-assessment of whether the request is complete enough to execute.

    Attributes:
        intent (str): The categorized user goal (e.g., 'register profile', 'search jobs').
        data (Dict[str, Any]): Key-value pairs of extracted entities (e.g., {'email': '...', 'keyword': '...'}).
        is_complete (bool): AI's determination of whether all required fields for the intent are present.
        missing_fields (List[str]): If is_complete is False, this lists what the user still needs to provide.
    """

    intent: str = Field(
        description="The identified user intent (e.g., 'register profile', 'get profiles', 'find similar jobs', etc.)"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Extracted entities needed for the intent"
    )
    is_complete: bool = Field(
        description="Whether all required fields for the intent are present"
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of missing required fields if is_complete is False",
    )


class EngineResponse(BaseModel):
    """
    The standardized return payload for all Engine operations.
    
    This model ensures that the `interface` layer always receives a consistent 
    response format, regardless of whether the operation was a database 
    lookup, an AI analysis, or a validation failure.

    Attributes:
        status (str): The outcome status (e.g., 'success', 'incomplete', 'error', 'unknown').
        message (str): A human-readable explanation or the final answer.
        data (Optional[Any]): The actual payload (e.g., a list of JobSchema objects).
    """

    status: str
    message: str
    data: Optional[Any] = None
