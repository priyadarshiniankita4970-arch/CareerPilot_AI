# CareerPilot AI — Full-Stack Job Portal

A runnable starter project with:
- **Frontend:** HTML, CSS, vanilla JavaScript (no React)
- **Backend:** Python + FastAPI
- **Database:** MongoDB
- Student and recruiter registration/login
- Seed script with 10 realistic sample jobs and a demo recruiter
- Student saved-job bookmarks stored in MongoDB
- Recruiter job CRUD
- Job search and filters
- Student job applications and application tracking
- Resume upload and rule-based skill matching
- Interview preparation questions and local rubric-based answer coaching
- Student dashboard with application tracking, saved jobs, personalized recommendations, notifications, resume builder, skill roadmap and mock interview practice
- Resume analyzer with keyword extraction, section checklist and improvement suggestions
- Recruiter dashboard with job management and applicant status updates
- Admin dashboard with user overview and job moderation
- Responsive UI with dark mode

## 1. Requirements
- Python 3.10+
- MongoDB Community Server running locally, OR a MongoDB Atlas connection string
- A browser

## 2. Setup on Windows CMD
Open Command Prompt and move to the folder containing this README and `requirements.txt`. For example:

```cmd
cd /d E:\CareerPilot_AI_HTML_CSS_JS_Python_MongoDB\CareerPilot_AI
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
copy .env.example .env
```

If `requirements.txt` is missing, make sure you are in the project root (the folder that contains `app`, `frontend`, and `requirements.txt`). Do not run `pip install -r requirements.txt` from a different directory.

## 3. Configure MongoDB
Edit `.env` and set your local or Atlas connection string. For local MongoDB:

```env
MONGODB_URL=mongodb://127.0.0.1:27017
DATABASE_NAME=careerpilot
JWT_SECRET=replace-this-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=5
```

Start the MongoDB Windows service if installed as a service:

```cmd
net start MongoDB
```

If you use MongoDB Atlas, put the Atlas URI in `MONGODB_URL` and ensure your database user and network access are configured.

## 4. Add demo data to MongoDB
With the virtual environment active and from the project root, run:

```cmd
python seed_demo_data.py
```

This inserts 10 sample jobs and creates a demo recruiter account. The script is safe to run again: it skips sample jobs already inserted by this script.

**Demo recruiter login**
- Email: `demo.recruiter@careerpilot.local`
- Password: `CareerPilotDemo123!`

This is for local demonstration only. Change the password or remove the demo account before deploying publicly.

**Demo administrator login**
- Email: `admin@careerpilot.local`
- Password: `CareerPilotAdmin123!`

This local demo administrator can review user/job counts and hide or reopen job listings. Do not deploy demo credentials publicly.

## 5. Run the application
From the project root, with the virtual environment active:

```cmd
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. API documentation is at `http://127.0.0.1:8000/docs`; health check is `http://127.0.0.1:8000/api/health`.

## Demo workflow
1. Register as a **Recruiter** and create a job.
2. Register a separate account as a **Student**.
3. Search jobs and apply.
4. Upload a PDF, DOCX, or TXT resume on the dashboard to compare extracted skills with a job's skills.
5. View application status from the student dashboard.
6. Recruiters can view applications for their own jobs and update statuses.
7. Students can save/bookmark jobs and find them in the dashboard.
8. Browse the API endpoints in `/docs` and check MongoDB connectivity at `/api/health`.

## Notes
- Passwords are hashed before storage.
- API routes use JWT bearer authentication.
- Resume files are stored locally in `uploads/`; resume metadata and extracted skills are stored in MongoDB. Saved jobs are also stored in MongoDB.
- Resume analysis and job recommendations use transparent local keyword/section heuristics; they do not call a hosted AI model and are not hiring predictions.
- Mock interview feedback uses a local rubric with answer-length and keyword coverage signals. Connect a provider API later if you want generative feedback.
- Resume builder saves structured profile data to MongoDB and exports a plain-text draft.
- Notifications are stored in MongoDB when an application is submitted or a recruiter changes its status.
- For production, add email verification, rate limiting, virus scanning, stronger file validation, HTTPS, and cloud file storage.

## Additional feature APIs
- `GET /api/recommendations` — personalized role suggestions based on uploaded resume skills
- `GET /api/notifications` and `PATCH /api/notifications/{id}/read` — user notifications
- `GET/POST /api/resume-builder` — save/read structured resume profile
- `POST /api/interview/evaluate` — local rubric-based answer feedback
- `GET /api/skill-roadmap?target_role=Python%20Developer` — role learning plan
- `GET/POST /api/skill-roadmap/progress` — save roadmap completion
- `GET /api/admin/overview` and `PATCH /api/admin/jobs/{id}/toggle` — admin overview and job moderation


## New student features (enhanced build)
- **ATS resume checker** — `POST /api/resume/ats-check` runs a transparent structure checklist and can compare extracted resume keywords with a selected job using `?job_id=...`.
- **Application success analytics** — `GET /api/analytics/applications` summarizes application statuses, shortlisted/hired outcomes, and monthly submissions.
- **Student portfolio generator** — `GET /api/portfolio` returns portfolio data from the saved resume profile; the dashboard can preview and download a standalone HTML portfolio.
- **More personalized recommendations** — `GET /api/recommendations` now considers skills from both the uploaded resume and saved resume-builder profile, plus role/headline relevance.

The ATS checklist is heuristic guidance, not a score from a commercial ATS provider and not a guarantee of interview selection. The application success rate is calculated as (shortlisted + hired) / total submitted applications.
