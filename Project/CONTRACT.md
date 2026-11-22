# CONTRACT.md

## Purpose 

Use this file to map each functinoality to component ownership and explicit interfaces. 

## Architecture Mapping

### Functionality 1: Chatbot Career Assistant (Resume FAQ)
- **interface**: Captures the user's text inquiry and PDF upload; manages resume persistence; renders the chatbot's feedback or error notifications to the screen.
- **engine**: Parses the PDF text and processes the user's question via a multimodal AI call to generate a context-aware professional response.
- **storage**: Manages the physical storage and retrieval of PDF files using unique IDs.

### Functionality 2: Professional Profile Setup & Management
- **interface**: Provides the multi-field profile form for registration and the interface for profile deletion.
- **engine**: Performs data validation, checks for required fields, and sanitizes input before processing registration or deletion requests.
- **storage**: Conducts lookups to prevent duplicate emails, persists professional profiles, and handles the removal of records from the member database.

### Functionality 3: Tailored Job Recommendation
- **interface**: Displays the "Find Job Matches" dashboard action and renders the final feed of job postings for the user.
- **engine**: Acts as the orchestrator; it fetches the user's profile context, determines the appropriate search criteria (major/headline), and filters the resulting job list for relevance.
- **storage**: Provides the member's profile data and executes a query against the job listing dataset based on the criteria provided by the engine.

### Functionality 4: Colleague Recommendation
- **interface**: Renders the "Connect With Peers" action and displays the list of recommended colleague profiles and their contact details.
- **engine**: Orchestrates the similarity logic; it retrieves the user's profile, defines the "matching" criteria (e.g., same major), and ensures the user is not recommended to themselves.
- **storage**: Conducts a double-lookup: first providing the requesting user's profile context and then executing a search for other members meeting the engine's similarity rules.

### Functionality 5: General Discovery (Guest Search)
- **interface**: Captures the search keyword and renders the list of matching professional profiles or job listings.
- **engine**: Determines whether the user is searching for people or jobs and validates the search keyword before dispatching to storage.
- **storage**: Executes a case-insensitive keyword search across relevant data fields for either profiles or jobs.

## Interface Contracts

### Functionality 1: Chatbot Career Assistant (Resume FAQ)
`interface -> engine`
- `analyze_resume_query(user_query: str, resume_file: pdf) -> response_payload`
- **Success:** `{"status": "success", "data": {"answer": "Your resume effectively highlights your leadership skills."}}`
- **Failure:** `{"status": "incomplete", "error": {"type": "missing_file", "message": "Please upload your resume in PDF format."}}`

### Functionality 2: Professional Profile Setup & Management
`interface -> engine`
- `process_profile_submission(profile_form: dict) -> response_payload`
- **Success:** `{"status": "success", "message": "Profile active"}`
- **Failure:** `{"status": "incomplete", "error": {"type": "validation_error", "missing_fields": ["headline", "major"]}}`
- **Conflict:** `{"status": "success", "message": "Already registered"}`

- `request_profile_deletion(email: str) -> response_payload`
- **Success:** `{"status": "success", "message": "Profile successfully deleted"}`
- **Failure:** `{"status": "success", "message": "Profile not found"}`

`engine -> storage`
- `store_professional_profile(profile_data: profile_record) -> response_payload`
- **Success:** `"Profile active"`
- **Failure:** `"Incomplete submission"` or `"Already registered"`

- `delete_profile(email: str) -> response_payload`
- **Success:** `"Profile successfully deleted"`
- **Failure:** `"Profile not found"`

### Functionality 3: Tailored Job Recommendation
`interface -> engine`
- `fetch_tailored_jobs(user_id: str) -> response_payload`
- **Success:** `{"status": "success", "data": { "jobs": [{"job_title": "Software Engineer", "company_name": "TechCorp"}]}}`
- **Failure:** `{"status": "success", "message": "No jobs can be found at the moment", "data": []}`

`engine -> storage (Step 1: Get User Profile)`
- `retrieve_member_context(user_id: str) -> response_payload`
- **Success:** `{"status": "success", "data": {"major": "Software Engineering", "years_experience": "3"}}`
- **Failure:** `{"status": "failure", "error": {"type": "profile_not_found", "message": "User profile is incomplete or missing."}}`

`engine -> storage (Step 2: Search Jobs)`
- `query_job_listings(criteria: dict) -> response_payload`
- **Success:** `{"status": "success", "data": { "jobs": [{"job_title": "...", "company_name": "..."}, ...]}}`
- **Failure:** `{"status": "success", "data": []}` (No matches) or `{"status": "failure", "error": {"type": "db_error"}}`

### Functionality 4: Colleague Recommendation
`interface -> engine`
- `fetch_colleague_recommendations(user_id: str) -> response_payload`
- **Success:** `{"status": "success", "data": {"colleagues": [{"full_name": "Jane Doe", "email": "jane.doe@email.com", "headline": "Senior Dev"}]}}`
- **Failure:** `{"status": "success", "message": "No similar colleagues found at this time.", "data": []}`

`engine -> storage (Step 1: Get User Profile)`
- `retrieve_member_context(user_id: str) -> response_payload`
- **Success:** `{"status": "success", "data": {"major": "Computer Science"}}`
- **Failure:** `{"status": "failure", "error": {"type": "profile_not_found"}}`

`engine -> storage (Step 2: Search Others)`
- `query_similar_profiles(criteria: dict) -> response_payload`
- **Success:** `{"status": "success", "data": {"matches": [{"full_name": "...", "email": "...", "headline": "..."}, ...]}}`
- **Failure:** `{"status": "success", "data": []}` (No matches)

### Functionality 5: General Discovery (Guest Search)
`interface -> engine`
- `search_general(keyword: str, target: str) -> response_payload`
- **Success:** `{"status": "success", "data": [...]}`
- **Failure:** `{"status": "incomplete", "message": "Please provide a search keyword.", "data": {"missing": ["keyword"]}}`

`engine -> storage`
- `search_members(keyword: str) -> response_payload`
- **Success:** `{"status": "success", "data": [MemberSchema, ...]}`
- **Failure:** `{"status": "success", "data": []}` (No matches)

- `query_job_listings(criteria: dict) -> response_payload`
- **Success:** `{"status": "success", "data": [JobSchema, ...]}`
- **Failure:** `{"status": "success", "data": []}` (No matches)
