# Personal tasks

## Purpose
Let authenticated users capture and view their own small task lists while
preventing one account from viewing or assigning tasks to another account.

## Requirements

### Requirement: Create personal tasks
The application SHALL accept nonblank task titles of at most 200 characters and
assign new tasks to the authenticated user using a CSRF-protected POST request.

#### Scenario: Create a valid task
- **WHEN** a logged-in user submits a valid title
- **THEN** the task is stored under that user's account and appears in their list

#### Scenario: Invalid title
- **WHEN** a blank or overlong title is submitted
- **THEN** the task is not created and a validation error is displayed

### Requirement: Private task lists
The application SHALL display only tasks owned by the authenticated user and
SHALL escape task titles when rendering HTML.

#### Scenario: Account isolation
- **WHEN** a user views their list
- **THEN** tasks owned by another account are absent

#### Scenario: Task title contains HTML
- **WHEN** a title containing HTML is displayed
- **THEN** it is rendered as text rather than executable markup
