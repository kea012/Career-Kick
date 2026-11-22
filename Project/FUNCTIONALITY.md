# FUNCTIONALITY.md

## Purpose
Define what the system should do, i.e., functionalities.

## Functionality

### Functionality 1: Chatbot Career Assistant (Resume FAQ)
- **Input:**
  - A user's natural-language question regarding a resume (e.g., "Does my resume sound professional?")
  - A user-uploaded resume in PDF format
- **Output:**
  - A natural-language response providing specific feedback based on the resume content
- **Success:**
  - The system successfully parses the PDF and returns a response relevant to the user's inquiry
- **Failure/Edge Cases:**
  - Question is unrelated to resumes -> return "I can only answer questions regarding resume quality and career content."
  - Uploaded file is not a PDF -> return "resume uploaded must be in pdf format"
  - Missing question or file -> prompt the user to enter a question and upload a document

### Functionality 2: Professional Profile Setup & Management
- **Input:**
  - **Registration:** A profile form including: Full name, professional email, headline, highest degree, major, graduation year, and total years of industry experience
  - **Deletion:** A request to remove a profile using a professional email
- **Output:**
  - Registration status message (`Profile active`, `Already registered`, or `Incomplete submission`)
  - Deletion status message (`Profile successfully deleted` or `Profile not found`)
- **Success:**
  - All mandatory profile fields are validated and the record is successfully saved to the member database, or an existing record is successfully removed
- **Failure/Edge Cases:**
  - Required fields are empty -> return `Incomplete submission` with a list of missing fields
  - Email address is already linked to an account -> return `Already registered`
  - Invalid data formatting (e.g., incorrect email syntax) -> return a validation error
  - Attempting to delete a non-existent profile -> return `Profile not found`

### Functionality 3: Tailored Job Recommendation
- **Input:** 
  - User triggers the "Find Job Matches" button on their dashboard (requires professional email)
- **Output:**
  - A curated list of job opportunities, each including: job title, company name, location, job summary, and an application link
- **Success:**
  - The system retrieves and displays a list of open positions that align with the education and experience stored in the user's profile
- **Failure/Edge Cases:**
  - No suitable jobs found -> return "No jobs can be found at the moment"
  - External job data source is unreachable -> return "Service error: External job data is currently unavailable."
  - Profile is not fully set up -> prompt the user to complete their profile before searching

### Functionality 4: Colleague Recommendation
- **Input:**
  - User triggers the "Connect With Peers" action on their dashboard (requires professional email)
- **Output:**
  - A list of recommended colleagues including: Full name, professional headline, major, and professional email contact
- **Success:**
  - The system identifies other members with similar professional backgrounds (e.g., same major) and displays their contact info, ensuring the user is not recommended to themselves
- **Failure/Edge Cases:**
  - No similar profiles found -> return "No similar colleagues found at this time."
  - Database connection error -> return "Service error: Unable to retrieve colleague data."
  - Profile is not fully set up -> prompt the user to complete their profile before searching

### Functionality 5: General Discovery (Guest Search)
- **Input:**
  - A search keyword entered by a user (guest or registered) to find either members or jobs (e.g., "Find someone in History" or "Jobs for Python")
- **Output:**
  - A list of matching member profiles or available job listings
- **Success:**
  - The system performs a case-insensitive search across multiple fields (name, major, headline for members; title, summary for jobs) and returns relevant results
- **Failure/Edge Cases:**
  - No matches found -> return a success message stating no results were found
  - Empty search query -> prompt the user to enter a keyword
