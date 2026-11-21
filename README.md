
# KU ResourceSavers
### Intelligent Campus Resource Exchange and Asset Management System

**Khalifa University — Group 7**

KU ResourceSavers is a Django-based web application designed to help university departments manage, share, reuse, repair, and track campus resources.

The system combines asset management, role-based approval workflows, sustainability monitoring, and Google Gemini AI to support more efficient resource utilization.

## 1. Project Features

### User Management
- Authentication and role-based access control.
- Administrator-created user accounts.
- Requester, Custodian, and Approver/Admin roles.
- Department-based approval responsibilities.
- Django Admin interface for managing users, groups, and system records.

### Asset Management
- Register and manage university assets.
- Categorize assets and assign departments.
- Track asset condition, lifecycle, and location.
- Support individual assets and bulk inventory lots.
- Publish and withdraw available assets.
- Search and filter campus resources.
- Manage asset specifications and attachments.
- Track inventory and stock movements.

### Resource Requests and Transfers
- Submit asset requests.
- Multi-stage approval workflows.
- Prevent unauthorized self-approval.
- Validate availability before reserving stock.
- Request expiration handling.
- Arrange and dispatch resource transfers.
- Confirm receipt and report disputes.
- Track request and transfer statuses.

### Maintenance and Disposition
- Report maintenance problems.
- Track maintenance and repair completion.
- Perform asset inspections.
- Manage retirement, donation, recycling, and disposal.

### AI Features
Google Gemini provides:
- Asset recommendations based on user requirements.
- Ranking of available matching resources.
- Explanations for recommendations.
- AI-assisted asset classification.
- Suggestions from existing asset categories.
- Human review of classification suggestions.
- AI-generated operational report summaries.
- Observations and data limitations.

AI recommendations do not automatically approve requests, reserve inventory, or modify asset records.

### Sustainability Dashboard
Displays recorded:
- Available inventory units.
- Reused units.
- Repaired units.
- Donated units.
- Recycled units.

The system also checks the completeness of estimated asset value and mass records.

These are recorded activity indicators, not verified environmental or financial savings.

### Reporting and Notifications
- Operational dashboard.
- Sustainability dashboard.
- Downloadable CSV reports.
- AI-generated management summaries.
- Request and transfer notifications.
- Notification inbox and read status.

---

## 2. Technologies

- Python
- Django 5.2.19
- MySQL
- HTML and CSS
- Google Gemini API
- Google GenAI Python SDK
- Git and GitHub

Dependencies are provided in `requirements.txt`.

## 3. Repository

GitHub:

https://github.com/A7mdmk/Asset-Management-Project-

Use the latest `main` branch for the complete application.

## 4. Installation and Setup

The following instructions are intended for local development on Windows.

### Step 1: Clone the repository

```powershell
git clone https://github.com/A7mdmk/Asset-Management-Project-.git
cd Asset-Management-Project-
```

### Step 2: Create a virtual environment

```powershell
py -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, adjust the execution policy for your current session or use the virtual environment's Python executable directly.

### Step 3: Install dependencies

```powershell
python -m pip install -r requirements.txt
```

A compatible Python installation, MySQL server, and any MySQL client build dependencies required by `mysqlclient` must be available.

### Step 4: Create the MySQL database

Start the MySQL server.

Using a MySQL administrator account, create the application's development database:

```sql
CREATE DATABASE ku_resourcesavers
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Create or select a local MySQL user and grant it the permissions required for Django migrations and testing.

For automated Django tests, the MySQL user must also have the necessary permissions to create and remove a separate test database.

### Step 5: Configure environment variables

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure:

```dotenv
DB_NAME=ku_resourcesavers
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
GEMINI_API_KEY=your_gemini_api_key
```

Replace the placeholder values with your own local credentials.

The Gemini API key is required for live AI features but is not required for tests that mock Gemini.

**Security:** Never commit `.env`, database passwords, or API keys to GitHub.

### Step 6: Apply database migrations

```powershell
python manage.py migrate
```

### Step 7: Create an administrator

```powershell
python manage.py createsuperuser
```

Enter the requested administrator account details.

### Step 8: Start the application

```powershell
python manage.py runserver
```

The local development server normally runs at:

http://127.0.0.1:8000/

**Important:** The root `/` URL is not currently assigned to a homepage. Use the application URLs in the next section.

---

## 5. Application URLs

### Login
http://127.0.0.1:8000/accounts/login/

### Main Dashboard
http://127.0.0.1:8000/accounts/dashboard/

### Django Administration
http://127.0.0.1:8000/admin/

### Asset Catalog
http://127.0.0.1:8000/assets/

### Asset Registration
http://127.0.0.1:8000/assets/register/

### AI Asset Classification
http://127.0.0.1:8000/assets/ai-classification/

### AI Asset Recommendations
http://127.0.0.1:8000/workflows/recommendations/

### Sustainability Dashboard
http://127.0.0.1:8000/assets/sustainability/

### Operational Reports
http://127.0.0.1:8000/assets/reports/

### AI Operational Reports
http://127.0.0.1:8000/assets/reports/ai/

Most features require authentication and appropriate permissions.

---

## 6. Administrator Access and User Management

KU ResourceSavers includes two interfaces:

**Django Administration**
- Used to manage user accounts, groups, categories, departments, and administrative records.
- Available at `/admin/`.
- Requires an authorized staff or superuser account.

**KU ResourceSavers Dashboard**
- Used for the application's resource-management features.
- Available at `/accounts/dashboard/`.
- Shows features according to the user's assigned role.

### Creating users and assigning roles

1. Log in to `/admin/` with a superuser account.
2. Open **Users**.
3. Create a user account.
4. Open the user's record.
5. Under **Groups**, assign the appropriate role:
   - `Requester`
   - `Custodian`
   - `Approver/Admin`
6. Save the user.

If the required groups do not exist, create them under **Authentication and Authorization > Groups** first.

Some approval workflows also require department-specific approver configuration. Configure the required departments and approver assignments before testing cross-department transfers.

Users can then log in through `/accounts/login/`.

**Note:** Django groups and permissions are distinct from Django staff/superuser flags. Assign only the access needed for each account.

### Local data

The repository contains application source code and migrations, not the contents of each developer's local MySQL database.

New installations require database setup, migrations, and local user accounts.

---

## 7. User Roles

### Requester
- Browse available assets.
- Search for resources.
- Use AI recommendations.
- Submit resource requests.
- Track request status.
- View notifications.

### Custodian
- Register and maintain assigned assets.
- Manage asset publications.
- Review inventory and stock.
- Use AI asset classification.
- Manage transfers and asset maintenance.
- Perform permitted inspections and disposition tasks.
- Access authorized reporting features.

### Approver/Admin
- Review authorized resource requests.
- Perform assigned approval responsibilities.
- Confirm applicable incoming transfers.
- View authorized reports and dashboards.

### System Administrator
- Configure application users and groups.
- Manage administrative records through Django Admin.
- Access privileged application functionality according to superuser and staff permissions.

---

## 8. Example End-to-End Workflow

1. An administrator creates the necessary accounts and roles.
2. A custodian registers an asset.
3. Gemini suggests an existing category for the asset.
4. The custodian reviews the suggestion before registration.
5. The custodian publishes the asset.
6. A requester searches for an available resource.
7. Gemini recommends relevant available assets.
8. The requester submits a resource request.
9. Authorized approvers review the request.
10. The application manages the reservation and transfer process.
11. The transfer is dispatched and receipt is confirmed.
12. Notifications and stock records reflect the workflow.
13. Operational reports summarize the recorded activity.
14. Sustainability indicators reflect applicable recorded events.
15. Gemini can generate a narrative report for human review.

The workflow is subject to inventory availability, role restrictions, department assignments, and approval requirements.

---

## 9. AI Implementation and Limitations

The application integrates Gemini through:

`workflows/gemini_client.py`

Relevant services:

- `workflows/ai_recommendations.py`
- `workflows/ai_classification.py`
- `assets/ai_reporting.py`

AI-generated content is validated where applicable and presented for human review.

The system does not allow AI recommendations to independently authorize transfers or change inventory.

AI-generated observations may contain inaccuracies and must be compared with verified database records.

### AI Recommendation Evaluation

The project includes a controlled synthetic benchmark.

Run:

```powershell
python manage.py shell -c "from workflows.ai_benchmark_runner import run_benchmark; run_benchmark()"
```

A previously recorded evaluation of four synthetic scenarios produced:

- Successful scenarios: 4/4
- Average Precision@3: 0.6667
- Average Recall@3: 1.0000

These results represent one recorded benchmark run, not a guarantee of performance on real-world requests.

The results can vary between Gemini executions.

---

## 10. Automated Testing

The project includes automated tests for:

- Asset registration and management.
- Authentication and permissions.
- Search and inventory.
- Requests and approval workflows.
- Transfers and concurrency.
- Notifications.
- Maintenance, inspections, and disposition.
- Sustainability calculations.
- Operational reporting and CSV export.
- AI recommendation evaluation.
- AI classification.
- AI-generated reports.

Run the complete Django test suite:

```powershell
python manage.py test
```

Run a specific test module:

```powershell
python manage.py test assets.test_ai_reporting
```

Run the system checks:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
```

An earlier full-suite result contained 671 tests. The subsequent AI Reporting implementation added 22 focused tests, and the full suite was reported as passing.

The expected total is approximately 693 tests, subject to verification against the current `main` branch.

Actual test results and screenshots should be recorded in the final testing report.

---

## 11. Project Structure

```text
Asset-Management-Project-/
|
|-- accounts/
|   |-- User authentication
|   |-- Role permissions
|   |-- Main dashboard
|
|-- assets/
|   |-- Asset models and services
|   |-- Asset registration and catalog
|   |-- Maintenance and inspections
|   |-- Sustainability calculations
|   |-- Operational reports
|   |-- AI-generated reporting
|
|-- workflows/
|   |-- Resource requests
|   |-- Approvals and transfers
|   |-- Notifications
|   |-- Gemini client
|   |-- AI recommendations
|   |-- AI classification
|   |-- AI evaluation
|
|-- config/
|   |-- Django settings and routing
|
|-- manage.py
|-- requirements.txt
|-- .env.example
|-- README.md
```

## 12. Project Documentation

The repository also includes project documentation developed during earlier phases, including:

- Phase 1 project documentation.
- Phase 2 documentation.
- Phase 3 requirements.
- Combined Phase 4 and Phase 5 documentation.

Final Phase 7 testing evidence and Phase 8 technical documentation should be maintained alongside the completed project deliverables.

## 13. Development and Deployment Notes

This implementation is configured primarily for local development and academic demonstration.

The current Django settings include development-oriented configuration, including `DEBUG=True` and a development secret key.

**Do not deploy the current settings to a public production server without security hardening.**

Before production deployment, use environment-based secret management, disable debug mode, configure allowed hosts, HTTPS, appropriate database permissions, and Django's deployment security settings.

Private asset attachments must remain access-controlled and must not be exposed through public static-file routes.

## 14. Team

**Khalifa University — Group 7**

- Ahmed Alkhoori
- Ali Alamim
- Suhail Alhammadi

The project was collaboratively developed using Git, GitHub feature branches, Pull Requests, and teammate reviews.

## 15. Academic Purpose

KU ResourceSavers was developed as a university software engineering project to demonstrate asset management, workflow automation, sustainable resource-sharing concepts, and responsible AI integration.
