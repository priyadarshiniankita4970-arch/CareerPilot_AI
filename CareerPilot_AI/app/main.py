import os, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from bson import ObjectId
from pymongo import DESCENDING
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document
from io import BytesIO

from .database import db, client, ensure_indexes
from .schemas import RegisterIn, LoginIn, JobIn, ApplicationStatusIn
from .security import hash_password, verify_password, create_access_token
from .dependencies import get_current_user, require_role

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = ROOT / UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))

app = FastAPI(title="CareerPilot AI API", version="2.0.0", description="Job portal API using FastAPI and MongoDB")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

SKILL_BANK = [
    "python", "fastapi", "django", "flask", "javascript", "html", "css", "react",
    "node.js", "express", "mongodb", "mysql", "sql", "git", "github", "docker",
    "aws", "java", "c++", "machine learning", "artificial intelligence", "data analysis",
    "pandas", "numpy", "communication", "problem solving", "rest api", "api", "linux"
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def clean_doc(doc):
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc

def public_user(user):
    return {"id": str(user["_id"]), "name": user["name"], "email": user["email"],
            "role": user["role"], "company": user.get("company", "")}

def serialize_job(job):
    job = clean_doc(job)
    job["recruiter_id"] = str(job["recruiter_id"])
    return job

def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            doc = Document(BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        if suffix == ".txt":
            return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return ""

def find_skills(text: str):
    lower = text.lower()
    return sorted({skill for skill in SKILL_BANK if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", lower)})

@app.on_event("startup")
async def startup():
    try:
        await client.admin.command("ping")
        await ensure_indexes()
        print("MongoDB connected.")
    except Exception as exc:
        print(f"WARNING: MongoDB connection failed: {exc}")
        print("Start MongoDB or update MONGODB_URL in .env.")

@app.get("/api/health")
async def health():
    try:
        await client.admin.command("ping")
        mongo = "connected"
    except Exception:
        mongo = "disconnected"
    return {"status": "ok", "mongodb": mongo}

@app.post("/api/auth/register", status_code=201)
async def register(data: RegisterIn):
    role = data.role.lower().strip()
    if role not in ("student", "recruiter"):
        raise HTTPException(status_code=400, detail="Role must be student or recruiter.")
    email = data.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if role == "recruiter" and not (data.company or "").strip():
        raise HTTPException(status_code=400, detail="Please enter your company name.")
    user_doc = {
        "name": data.name.strip(), "email": email, "password_hash": hash_password(data.password),
        "role": role, "company": (data.company or "").strip() if role == "recruiter" else "",
        "created_at": now_iso()
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    token = create_access_token(str(result.inserted_id), role)
    return {"token": token, "user": public_user(user_doc)}

@app.post("/api/auth/login")
async def login(data: LoginIn):
    user = await db.users.find_one({"email": data.email.lower().strip()})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return {"token": create_access_token(str(user["_id"]), user["role"]), "user": public_user(user)}

@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return {"user": user}

@app.get("/api/jobs")
async def list_jobs(search: str = "", location: str = "", job_type: str = "", page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=50)):
    query = {"is_active": True}
    if search.strip():
        terms = [re.escape(x) for x in search.strip().split()[:6]]
        query["$or"] = [{"title": {"$regex": "|".join(terms), "$options": "i"}},
                        {"company": {"$regex": "|".join(terms), "$options": "i"}},
                        {"description": {"$regex": "|".join(terms), "$options": "i"}},
                        {"skills": {"$elemMatch": {"$regex": "|".join(terms), "$options": "i"}}}]
    if location.strip():
        query["location"] = {"$regex": re.escape(location.strip()), "$options": "i"}
    if job_type.strip():
        query["job_type"] = job_type.strip()
    total = await db.jobs.count_documents(query)
    cursor = db.jobs.find(query).sort("created_at", DESCENDING).skip((page - 1) * limit).limit(limit)
    jobs = [serialize_job(x) async for x in cursor]
    return {"items": jobs, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "is_active": True})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job": serialize_job(job)}


@app.get("/api/saved-jobs")
async def list_saved_jobs(user=Depends(require_role("student"))):
    saved = [x async for x in db.saved_jobs.find({"student_id": ObjectId(user["id"])}).sort("created_at", DESCENDING)]
    items = []
    for entry in saved:
        job = await db.jobs.find_one({"_id": entry["job_id"], "is_active": True})
        if job:
            item = serialize_job(job)
            item["saved_at"] = entry.get("created_at", "")
            items.append(item)
    return {"items": items, "total": len(items)}

@app.post("/api/jobs/{job_id}/save", status_code=201)
async def save_job(job_id: str, user=Depends(require_role("student"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "is_active": True})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    await db.saved_jobs.update_one(
        {"student_id": ObjectId(user["id"]), "job_id": ObjectId(job_id)},
        {"$setOnInsert": {"student_id": ObjectId(user["id"]), "job_id": ObjectId(job_id), "created_at": now_iso()}},
        upsert=True
    )
    return {"message": "Job saved to your list."}

@app.delete("/api/jobs/{job_id}/save")
async def unsave_job(job_id: str, user=Depends(require_role("student"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    result = await db.saved_jobs.delete_one({"student_id": ObjectId(user["id"]), "job_id": ObjectId(job_id)})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="This job is not in your saved list.")
    return {"message": "Job removed from your saved list."}

@app.post("/api/jobs", status_code=201)
async def create_job(data: JobIn, user=Depends(require_role("recruiter"))):
    skills = list(dict.fromkeys([s.strip() for s in data.skills if s.strip()]))[:30]
    doc = {**data.model_dump(), "skills": skills, "recruiter_id": ObjectId(user["id"]),
           "created_at": now_iso(), "updated_at": now_iso(), "is_active": True}
    result = await db.jobs.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"job": serialize_job(doc)}

@app.put("/api/jobs/{job_id}")
async def update_job(job_id: str, data: JobIn, user=Depends(require_role("recruiter"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    doc = await db.jobs.find_one({"_id": ObjectId(job_id), "recruiter_id": ObjectId(user["id"])})
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found or you do not own it.")
    updates = data.model_dump()
    updates["skills"] = list(dict.fromkeys([s.strip() for s in data.skills if s.strip()]))[:30]
    updates["updated_at"] = now_iso()
    await db.jobs.update_one({"_id": doc["_id"]}, {"$set": updates})
    updated = await db.jobs.find_one({"_id": doc["_id"]})
    return {"job": serialize_job(updated)}

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, user=Depends(require_role("recruiter"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    result = await db.jobs.update_one({"_id": ObjectId(job_id), "recruiter_id": ObjectId(user["id"])}, {"$set": {"is_active": False, "updated_at": now_iso()}})
    if not result.modified_count:
        raise HTTPException(status_code=404, detail="Job not found or you do not own it.")
    return {"message": "Job closed successfully."}

@app.post("/api/jobs/{job_id}/apply", status_code=201)
async def apply_job(job_id: str, user=Depends(require_role("student"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "is_active": True})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    try:
        result = await db.applications.insert_one({
            "job_id": job["_id"], "student_id": ObjectId(user["id"]), "recruiter_id": job["recruiter_id"],
            "status": "Applied", "created_at": now_iso(), "updated_at": now_iso()
        })
    except Exception:
        raise HTTPException(status_code=409, detail="You have already applied for this job.")
    await db.notifications.insert_one({
        "user_id": ObjectId(user["id"]), "kind": "application",
        "title": "Application submitted", "message": f"Your application for {job.get('title', 'this role')} at {job.get('company', '')} was submitted.",
        "read": False, "created_at": now_iso()
    })
    await db.notifications.insert_one({
        "user_id": job["recruiter_id"], "kind": "new_application",
        "title": "New job application", "message": f"{user.get('name', 'A student')} applied for {job.get('title', 'your job')}.",
        "read": False, "created_at": now_iso()
    })
    return {"message": "Application submitted successfully.", "application_id": str(result.inserted_id)}

@app.get("/api/applications/mine")
async def my_applications(user=Depends(require_role("student"))):
    apps = [x async for x in db.applications.find({"student_id": ObjectId(user["id"])}).sort("created_at", DESCENDING)]
    output = []
    for a in apps:
        job = await db.jobs.find_one({"_id": a["job_id"]})
        output.append({"id": str(a["_id"]), "job_id": str(a["job_id"]), "status": a["status"],
                       "created_at": a["created_at"], "job_title": job.get("title", "Deleted job") if job else "Deleted job",
                       "company": job.get("company", "") if job else "", "location": job.get("location", "") if job else ""})
    return {"items": output}

@app.get("/api/recruiter/jobs")
async def recruiter_jobs(user=Depends(require_role("recruiter"))):
    jobs = [serialize_job(j) async for j in db.jobs.find({"recruiter_id": ObjectId(user["id"])}).sort("created_at", DESCENDING)]
    for job in jobs:
        job["application_count"] = await db.applications.count_documents({"job_id": ObjectId(job["id"])})
    return {"items": jobs}

@app.get("/api/recruiter/applications")
async def recruiter_applications(user=Depends(require_role("recruiter"))):
    apps = [x async for x in db.applications.find({"recruiter_id": ObjectId(user["id"])}).sort("created_at", DESCENDING)]
    output = []
    for a in apps:
        job = await db.jobs.find_one({"_id": a["job_id"]})
        student = await db.users.find_one({"_id": a["student_id"]})
        output.append({"id": str(a["_id"]), "job_id": str(a["job_id"]), "job_title": job.get("title", "Deleted job") if job else "Deleted job",
                       "student_name": student.get("name", "Student") if student else "Student",
                       "student_email": student.get("email", "") if student else "", "status": a["status"], "created_at": a["created_at"]})
    return {"items": output}

@app.patch("/api/recruiter/applications/{application_id}")
async def update_application(application_id: str, data: ApplicationStatusIn, user=Depends(require_role("recruiter"))):
    allowed = {"Reviewing", "Shortlisted", "Rejected", "Hired"}
    if data.status not in allowed:
        raise HTTPException(status_code=400, detail="Status must be Reviewing, Shortlisted, Rejected, or Hired.")
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID.")
    result = await db.applications.update_one({"_id": ObjectId(application_id), "recruiter_id": ObjectId(user["id"])},
                                              {"$set": {"status": data.status, "updated_at": now_iso()}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Application not found.")
    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if application:
        job = await db.jobs.find_one({"_id": application["job_id"]})
        await db.notifications.insert_one({
            "user_id": application["student_id"], "kind": "status",
            "title": "Application status updated",
            "message": f"Your application for {(job or {}).get('title', 'a job')} is now {data.status}.",
            "read": False, "created_at": now_iso()
        })
    return {"message": "Application status updated."}

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...), user=Depends(require_role("student"))):
    allowed = {".pdf", ".docx", ".txt"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Upload a PDF, DOCX, or TXT file.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File must be smaller than {MAX_UPLOAD_MB} MB.")
    text = extract_text(file.filename or "resume", content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not read text from this file. Try a text-based PDF, DOCX, or TXT.")
    safe_name = f"{user['id']}_{uuid.uuid4().hex}{suffix}"
    path = UPLOAD_DIR / safe_name
    path.write_bytes(content)
    skills = find_skills(text)
    await db.resumes.update_one({"user_id": ObjectId(user["id"])},
        {"$set": {"user_id": ObjectId(user["id"]), "original_name": Path(file.filename).name,
                  "stored_name": safe_name, "skills": skills, "extracted_text": text[:30000], "uploaded_at": now_iso()}}, upsert=True)
    lower_text = text.lower()
    section_checks = {
        "contact details": any(x in lower_text for x in ["@", "linkedin", "phone", "mobile"]),
        "professional summary": any(x in lower_text for x in ["summary", "objective", "profile"]),
        "education": "education" in lower_text or "qualification" in lower_text,
        "experience or internship": any(x in lower_text for x in ["experience", "internship", "employment"]),
        "projects": "project" in lower_text,
        "skills": "skill" in lower_text or bool(skills),
    }
    quality_score = round(100 * sum(section_checks.values()) / len(section_checks))
    suggestions = [f"Consider adding a clear {label} section." for label, found in section_checks.items() if not found]
    await db.resumes.update_one({"user_id": ObjectId(user["id"])}, {"$set": {
        "analysis": {"quality_score": quality_score, "section_checks": section_checks, "suggestions": suggestions}
    }})
    return {"message": "Resume uploaded and analyzed.", "filename": Path(file.filename).name, "skills": skills,
            "skills_count": len(skills), "quality_score": quality_score, "section_checks": section_checks,
            "suggestions": suggestions,
            "note": "Resume checks and skill extraction are rule-based guidance, not an AI model or hiring prediction."}

@app.get("/api/resume/match/{job_id}")
async def match_resume(job_id: str, user=Depends(require_role("student"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    resume = await db.resumes.find_one({"user_id": ObjectId(user["id"])})
    if not resume:
        raise HTTPException(status_code=404, detail="Upload your resume first.")
    job = await db.jobs.find_one({"_id": ObjectId(job_id), "is_active": True})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    resume_skills = {s.lower() for s in resume.get("skills", [])}
    required = {s.lower().strip() for s in job.get("skills", []) if s.strip()}
    matched = sorted(resume_skills & required)
    missing = sorted(required - resume_skills)
    score = round(len(matched) / len(required) * 100) if required else 0
    return {"score": score, "matched_skills": matched, "missing_skills": missing,
            "resume_skills": sorted(resume_skills), "message": "This is a keyword-based estimate, not an employment prediction."}

@app.get("/api/interview/questions")
async def interview_questions(role: str = "Python Developer", level: str = "Beginner"):
    pools = {
        "python": [
            ("What is the difference between a list and a tuple?", "Lists are mutable; tuples are immutable."),
            ("What is a Python dictionary?", "A key-value data structure with unique keys."),
            ("What is the purpose of exception handling?", "try/except lets code handle errors without crashing unexpectedly."),
            ("What is a decorator?", "A callable that wraps another function to extend or modify its behavior."),
            ("What is the difference between synchronous and asynchronous code?", "Synchronous code runs step by step; asynchronous code can yield while waiting for I/O.")
        ],
        "fastapi": [
            ("What is FastAPI?", "A Python framework for building APIs with type hints and automatic documentation."),
            ("What is dependency injection in FastAPI?", "A way to declare reusable dependencies that FastAPI resolves for each request."),
            ("What is Pydantic used for?", "Validating and parsing request data using Python type annotations."),
            ("What is the difference between PUT and PATCH?", "PUT generally replaces a resource; PATCH updates selected fields."),
            ("What is an HTTP status code 401?", "It indicates that valid authentication credentials are missing or invalid.")
        ],
        "sql": [
            ("What is a primary key?", "A column or set of columns that uniquely identifies each row."),
            ("What is the difference between INNER JOIN and LEFT JOIN?", "INNER JOIN returns matches; LEFT JOIN also preserves all rows from the left table."),
            ("What does an index do?", "It can speed up reads, at the cost of storage and some write overhead.")
        ],
        "general": [
            ("Tell me about a project you built.", "Explain the problem, your role, the technology, one challenge, and the outcome."),
            ("How do you debug a problem?", "Reproduce it, inspect logs, isolate the cause, test a fix, and add regression coverage."),
            ("How do you handle a deadline?", "Break the work into priorities, communicate risks early, and deliver the highest-value pieces first.")
        ]
    }
    r = role.lower()
    key = "fastapi" if "fastapi" in r else "sql" if "sql" in r or "database" in r else "python" if "python" in r or "developer" in r else "general"
    items = pools[key] + pools["general"]
    if level.lower() == "advanced":
        items = list(reversed(items))
    return {"role": role, "level": level, "items": [{"question": q, "sample_answer": a} for q, a in items[:8]],
            "note": "Practice prompts and sample answers; tailor answers to your own experience."}

@app.get("/api/dashboard")
async def dashboard(user=Depends(get_current_user)):
    if user["role"] == "student":
        applications = await db.applications.count_documents({"student_id": ObjectId(user["id"])})
        resume = await db.resumes.find_one({"user_id": ObjectId(user["id"])})
        return {"role": "student", "applications": applications, "resume_uploaded": bool(resume),
                "resume_skills": resume.get("skills", []) if resume else [], "jobs_available": await db.jobs.count_documents({"is_active": True})}
    if user["role"] == "recruiter":
        jobs = await db.jobs.count_documents({"recruiter_id": ObjectId(user["id"]), "is_active": True})
        apps = await db.applications.count_documents({"recruiter_id": ObjectId(user["id"])})
        return {"role": "recruiter", "active_jobs": jobs, "applications_received": apps}
    if user["role"] == "admin":
        return {"role": "admin", "users": await db.users.count_documents({}),
                "students": await db.users.count_documents({"role": "student"}),
                "recruiters": await db.users.count_documents({"role": "recruiter"}),
                "jobs": await db.jobs.count_documents({}),
                "active_jobs": await db.jobs.count_documents({"is_active": True}),
                "applications": await db.applications.count_documents({})}
    raise HTTPException(status_code=403, detail="Unsupported account role.")



# --- CareerPilot AI extended features (MongoDB-backed) ---
from pydantic import BaseModel, Field
from typing import List as TypingList

class ResumeBuilderIn(BaseModel):
    headline: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=2000)
    education: str = Field(default="", max_length=3000)
    experience: str = Field(default="", max_length=4000)
    skills: TypingList[str] = Field(default_factory=list, max_length=60)
    projects: str = Field(default="", max_length=4000)
    links: str = Field(default="", max_length=500)

class InterviewAnswerIn(BaseModel):
    role: str = Field(default="Python Developer", max_length=100)
    question: str = Field(min_length=5, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    expected_keywords: TypingList[str] = Field(default_factory=list, max_length=30)

@app.get("/api/recommendations")
async def recommendations(user=Depends(require_role("student"))):
    resume = await db.resumes.find_one({"user_id": ObjectId(user["id"])})
    profile = await db.resume_profiles.find_one({"user_id": ObjectId(user["id"])}) or {}
    student_skills = {s.lower() for s in (resume or {}).get("skills", [])}
    student_skills.update(s.lower() for s in profile.get("skills", []))
    preference_text = " ".join([profile.get("headline", ""), profile.get("summary", "")]).lower()
    applied_ids = {a["job_id"] async for a in db.applications.find({"student_id": ObjectId(user["id"])}, {"job_id": 1})}
    saved_ids = {a["job_id"] async for a in db.saved_jobs.find({"student_id": ObjectId(user["id"])}, {"job_id": 1})}
    items = []
    async for job in db.jobs.find({"is_active": True}).sort("created_at", DESCENDING).limit(100):
        required = {str(s).lower() for s in job.get("skills", [])}
        matched = sorted(student_skills & required)
        score = round(100 * len(matched) / max(1, len(required))) if required else 0
        title_terms = [w for w in re.findall(r"[a-zA-Z+#.]+", job.get("title", "").lower()) if len(w) > 2]
        preference_hits = sum(1 for term in title_terms if term in preference_text)
        if preference_hits:
            score = min(100, score + min(15, preference_hits * 5))
        if not student_skills and not preference_text:
            score = 0
        if job["_id"] in applied_ids:
            continue
        item = serialize_job(job)
        item.update({"match_score": score, "matched_skills": matched,
                     "already_saved": job["_id"] in saved_ids,
                     "recommendation_reason": ("Matches your skills: " + ", ".join(matched)) if matched else "Build the listed skills to improve your fit"})
        items.append(item)
    items.sort(key=lambda x: (x["match_score"], x["created_at"]), reverse=True)
    return {"items": items[:12], "note": "Recommendations use transparent keyword overlap from your uploaded resume, not an employment prediction."}



@app.get("/api/analytics/applications")
async def application_analytics(user=Depends(require_role("student"))):
    docs = [a async for a in db.applications.find({"student_id": ObjectId(user["id"])}).sort("created_at", 1)]
    counts = {"Applied": 0, "Reviewing": 0, "Shortlisted": 0, "Rejected": 0, "Hired": 0}
    monthly = {}
    for item in docs:
        status = item.get("status", "Applied")
        counts[status] = counts.get(status, 0) + 1
        month = (item.get("created_at") or "")[:7]
        if month:
            monthly[month] = monthly.get(month, 0) + 1
    total = len(docs)
    positive = counts.get("Shortlisted", 0) + counts.get("Hired", 0)
    return {"total": total, "status_counts": counts,
            "positive_outcomes": positive,
            "success_rate": round(100 * positive / total) if total else 0,
            "monthly": [{"month": k, "applications": v} for k, v in sorted(monthly.items())],
            "note": "Success rate means shortlisted or hired applications divided by all submitted applications. It is descriptive, not a prediction."}

@app.post("/api/resume/ats-check")
async def ats_resume_check(job_id: Optional[str] = None, user=Depends(require_role("student"))):
    resume = await db.resumes.find_one({"user_id": ObjectId(user["id"])})
    if not resume or not resume.get("extracted_text"):
        raise HTTPException(status_code=404, detail="Upload a readable resume before running the ATS check.")
    text = resume.get("extracted_text", "")
    lower = text.lower()
    checks = {
        "Contact information": any(x in lower for x in ["@", "linkedin", "phone", "mobile"]),
        "Professional summary": any(x in lower for x in ["summary", "objective", "profile"]),
        "Education": "education" in lower or "qualification" in lower,
        "Experience": any(x in lower for x in ["experience", "internship", "employment"]),
        "Projects": "project" in lower,
        "Skills": "skill" in lower or bool(resume.get("skills")),
        "Readable text": len(text.strip()) >= 250,
        "Action verbs": any(x in lower for x in ["developed", "created", "implemented", "designed", "built", "improved"]),
    }
    missing = [k for k, v in checks.items() if not v]
    matched, missing_keywords = [], []
    if job_id:
        if not ObjectId.is_valid(job_id):
            raise HTTPException(status_code=400, detail="Invalid job ID.")
        job = await db.jobs.find_one({"_id": ObjectId(job_id), "is_active": True})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        terms = list(dict.fromkeys([str(x).lower().strip() for x in job.get("skills", []) if str(x).strip()]))
        matched = [x for x in terms if re.search(r"(?<![a-z0-9])" + re.escape(x) + r"(?![a-z0-9])", lower)]
        missing_keywords = [x for x in terms if x not in matched]
    score = round(100 * sum(checks.values()) / len(checks))
    suggestions = [f"Add or improve the {x.lower()} section." for x in missing]
    if missing_keywords:
        suggestions.append("Where accurate, include these job keywords: " + ", ".join(missing_keywords))
    if not suggestions:
        suggestions.append("Your resume covers the main structural checks. Tailor bullet points to the target role.")
    return {"ats_score": score, "checks": checks, "missing_sections": missing,
            "matched_keywords": matched, "missing_keywords": missing_keywords,
            "suggestions": suggestions,
            "disclaimer": "This is a transparent rule-based checklist, not a real ATS vendor score or guarantee of selection."}

@app.get("/api/portfolio")
async def generate_portfolio_data(user=Depends(require_role("student"))):
    profile = await db.resume_profiles.find_one({"user_id": ObjectId(user["id"])}, {"_id": 0, "user_id": 0}) or {}
    resume = await db.resumes.find_one({"user_id": ObjectId(user["id"])}) or {}
    return {"name": user.get("name", ""), "email": user.get("email", ""),
            "headline": profile.get("headline", "Aspiring Professional"),
            "summary": profile.get("summary", ""), "education": profile.get("education", ""),
            "experience": profile.get("experience", ""), "projects": profile.get("projects", ""),
            "skills": profile.get("skills", []) or resume.get("skills", []),
            "links": profile.get("links", "")}

@app.get("/api/notifications")
async def get_notifications(user=Depends(get_current_user)):
    items = []
    async for n in db.notifications.find({"user_id": ObjectId(user["id"])}).sort("created_at", DESCENDING).limit(50):
        n["id"] = str(n.pop("_id"))
        n["user_id"] = str(n["user_id"])
        items.append(n)
    return {"items": items, "unread": sum(1 for x in items if not x.get("read"))}

@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user=Depends(get_current_user)):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID.")
    result = await db.notifications.update_one({"_id": ObjectId(notification_id), "user_id": ObjectId(user["id"])}, {"$set": {"read": True}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"message": "Notification marked as read."}

@app.post("/api/resume-builder")
async def save_resume_builder(data: ResumeBuilderIn, user=Depends(require_role("student"))):
    doc = data.model_dump()
    doc["skills"] = list(dict.fromkeys(s.strip() for s in data.skills if s.strip()))[:60]
    doc.update({"user_id": ObjectId(user["id"]), "updated_at": now_iso()})
    await db.resume_profiles.update_one({"user_id": ObjectId(user["id"])}, {"$set": doc}, upsert=True)
    return {"message": "Resume profile saved.", "resume": {**doc, "user_id": user["id"]}}

@app.get("/api/resume-builder")
async def get_resume_builder(user=Depends(require_role("student"))):
    doc = await db.resume_profiles.find_one({"user_id": ObjectId(user["id"])}, {"_id": 0, "user_id": 0})
    return {"resume": doc or {"headline": "", "summary": "", "education": "", "experience": "", "skills": [], "projects": "", "links": ""}}

@app.post("/api/interview/evaluate")
async def evaluate_interview(data: InterviewAnswerIn, user=Depends(require_role("student"))):
    # Local explainable coaching rubric; does not call an external AI provider.
    answer = data.answer.strip()
    keywords = [k.strip() for k in data.expected_keywords if k.strip()]
    if not keywords:
        defaults = {
            "python": ["mutable", "immutable", "function", "object", "exception", "list", "dictionary"],
            "api": ["request", "response", "endpoint", "http", "status"],
            "database": ["query", "table", "collection", "index", "data"],
            "fastapi": ["endpoint", "pydantic", "validation", "dependency", "async"],
        }
        key = next((k for k in defaults if k in (data.role + " " + data.question).lower()), "python")
        keywords = defaults[key]
    lower = answer.lower()
    found = [k for k in keywords if k.lower() in lower]
    coverage = round(100 * len(found) / max(1, len(keywords)))
    length_score = min(25, round(len(answer.split()) / 4))
    structure_score = 15 if any(x in lower for x in ["because", "for example", "therefore", "such as", "first"]) else 5
    score = min(100, round(coverage * .6 + length_score + structure_score))
    if len(answer.split()) < 12:
        feedback = "Add more detail. Explain the concept, give a short example, and describe when you would use it."
    elif coverage < 35:
        feedback = "Your answer has some detail, but include more core technical terms and explain them in context."
    elif score >= 75:
        feedback = "Good structure. Keep it concise and add a concrete example from a project or practice exercise."
    else:
        feedback = "Good start. Define the concept clearly, explain why it matters, and include a practical example."
    attempt = {"user_id": ObjectId(user["id"]), "role": data.role, "question": data.question, "answer": answer,
               "score": score, "matched_keywords": found, "feedback": feedback, "created_at": now_iso()}
    await db.interview_attempts.insert_one(attempt)
    return {"score": score, "matched_keywords": found, "suggested_keywords": [k for k in keywords if k not in found],
            "feedback": feedback, "note": "This is a local rubric-based practice score, not an AI model or hiring assessment."}

@app.get("/api/skill-roadmap")
async def skill_roadmap(target_role: str = "Python Developer", user=Depends(require_role("student"))):
    resume = await db.resumes.find_one({"user_id": ObjectId(user["id"])})
    owned = {s.lower() for s in (resume or {}).get("skills", [])}
    role = target_role.lower()
    tracks = {
      "python": ["Python fundamentals", "Functions and OOP", "SQL and database design", "REST APIs with FastAPI", "Authentication and testing", "Deploy a portfolio API"],
      "frontend": ["HTML semantics", "Responsive CSS", "JavaScript DOM and async", "REST API integration", "Accessibility and testing", "Deploy a portfolio website"],
      "data": ["Python basics", "SQL queries and joins", "Pandas data cleaning", "Statistics fundamentals", "Data visualization", "Build an end-to-end analysis project"],
      "ai": ["Python and NumPy", "Pandas and data preparation", "Statistics and evaluation", "Machine-learning fundamentals", "Model serving with an API", "Document a reproducible AI project"]
    }
    key = "frontend" if any(x in role for x in ["frontend", "web", "ui"]) else "data" if any(x in role for x in ["data", "analyst", "sql"]) else "ai" if any(x in role for x in ["ai", "ml", "machine"]) else "python"
    steps = tracks[key]
    return {"target_role": target_role, "completed_skills": sorted(owned), "steps": [
      {"title": title, "done": any(token in " ".join(owned) for token in title.lower().split() if len(token) > 3),
       "deliverable": f"Complete one small exercise or project for: {title}"} for title in steps],
      "note": "Suggested learning sequence. Marking progress is available through the roadmap progress endpoint."}

@app.post("/api/skill-roadmap/progress")
async def save_roadmap_progress(data: dict, user=Depends(require_role("student"))):
    title = str(data.get("title", "")).strip()[:200]
    done = bool(data.get("done", False))
    if not title:
        raise HTTPException(status_code=400, detail="A roadmap step title is required.")
    await db.roadmap_progress.update_one({"user_id": ObjectId(user["id"]), "title": title},
        {"$set": {"user_id": ObjectId(user["id"]), "title": title, "done": done, "updated_at": now_iso()}}, upsert=True)
    return {"message": "Roadmap progress saved."}

@app.get("/api/skill-roadmap/progress")
async def get_roadmap_progress(user=Depends(require_role("student"))):
    items = []
    async for x in db.roadmap_progress.find({"user_id": ObjectId(user["id"])}):
        items.append({"title": x["title"], "done": x.get("done", False)})
    return {"items": items}

@app.get("/api/admin/overview")
async def admin_overview(user=Depends(require_role("admin"))):
    latest_users = []
    async for x in db.users.find({}, {"password_hash": 0}).sort("created_at", DESCENDING).limit(30):
        latest_users.append({"id": str(x["_id"]), "name": x.get("name", ""), "email": x.get("email", ""),
                             "role": x.get("role", ""), "created_at": x.get("created_at", "")})
    latest_jobs = []
    async for x in db.jobs.find({}).sort("created_at", DESCENDING).limit(30):
        latest_jobs.append({"id": str(x["_id"]), "title": x.get("title", ""), "company": x.get("company", ""),
                            "is_active": x.get("is_active", False), "created_at": x.get("created_at", "")})
    return {"users": latest_users, "jobs": latest_jobs}

@app.patch("/api/admin/jobs/{job_id}/toggle")
async def admin_toggle_job(job_id: str, user=Depends(require_role("admin"))):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    await db.jobs.update_one({"_id": job["_id"]}, {"$set": {"is_active": not job.get("is_active", False), "updated_at": now_iso()}})
    return {"message": "Job visibility updated.", "is_active": not job.get("is_active", False)}


@app.get("/")
async def home():
    return FileResponse(FRONTEND / "index.html")

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
