# Authentication

## Purpose
Provide session-based login and logout for the local todo application so each
person can access a private task list using their own account credentials.

## Requirements

### Requirement: Authenticated task access
The application SHALL require a valid authenticated session to access task pages.

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor opens the task list
- **THEN** the application redirects them to the login form

#### Scenario: Correct credentials
- **WHEN** a user submits valid credentials
- **THEN** a session is established and their task list is displayed

#### Scenario: Incorrect credentials
- **WHEN** a user submits invalid credentials
- **THEN** login fails without establishing a session

### Requirement: Session logout
The application SHALL allow a logged-in user to end their session through a
CSRF-protected POST request.

#### Scenario: Sign out
- **WHEN** a logged-in user signs out
- **THEN** their session ends and the login page is displayed
