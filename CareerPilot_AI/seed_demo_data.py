"""Insert repeatable demo users and jobs into the configured MongoDB database.

Run from the project root: python seed_demo_data.py
Demo recruiter login: demo.recruiter@careerpilot.local / CareerPilotDemo123!
"""
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from bson import ObjectId
from app.database import client, db, ensure_indexes
from app.security import hash_password

load_dotenv()

DEMO_EMAIL = "demo.recruiter@careerpilot.local"
DEMO_PASSWORD = "CareerPilotDemo123!"

JOBS = [
    {"title": "Python Developer Intern", "company": "NovaByte Technologies", "location": "Bhubaneswar, Odisha", "job_type": "Internship", "salary": "₹8,000–₹15,000/month", "experience": "Fresher", "skills": ["Python", "FastAPI", "MongoDB", "REST API", "Git"], "description": "Work with the backend team to build and test REST APIs, write readable Python code, and connect services to MongoDB. Suitable for students who enjoy learning by building projects."},
    {"title": "Junior Full Stack Developer", "company": "PixelRoute Labs", "location": "Remote", "job_type": "Full-time", "salary": "₹3–5 LPA", "experience": "0–1 year", "skills": ["HTML", "CSS", "JavaScript", "Python", "REST API"], "description": "Help build responsive web experiences and backend endpoints. Collaborate with designers and developers, review code, and improve product quality."},
    {"title": "Data Analyst Trainee", "company": "InsightSpring", "location": "Bengaluru, Karnataka", "job_type": "Full-time", "salary": "₹3–4.5 LPA", "experience": "Fresher", "skills": ["Python", "SQL", "Excel", "Pandas", "Data Analysis"], "description": "Clean datasets, prepare reports, and communicate useful insights. Candidates should know basic SQL and Python and be willing to learn analytics tools."},
    {"title": "AI/ML Intern", "company": "CognitiveCraft AI", "location": "Hyderabad, Telangana", "job_type": "Internship", "salary": "₹10,000–₹20,000/month", "experience": "Fresher", "skills": ["Python", "Machine Learning", "Pandas", "NumPy", "Artificial Intelligence"], "description": "Support experiments for machine-learning prototypes, prepare datasets, compare model results, and document findings with guidance from mentors."},
    {"title": "Frontend Developer", "company": "BrightCanvas Digital", "location": "Pune, Maharashtra", "job_type": "Full-time", "salary": "₹3.5–6 LPA", "experience": "0–2 years", "skills": ["HTML", "CSS", "JavaScript", "React", "GitHub"], "description": "Create accessible, responsive user interfaces and reusable components. Work with APIs and test layouts across desktop and mobile screens."},
    {"title": "FastAPI Backend Trainee", "company": "CloudHarbor Systems", "location": "Bhubaneswar, Odisha", "job_type": "Full-time", "salary": "₹2.8–4 LPA", "experience": "Fresher", "skills": ["Python", "FastAPI", "MongoDB", "JWT", "REST API"], "description": "Build API endpoints, validate request data, implement authentication, and work with MongoDB collections. A project portfolio and curiosity are valued."},
    {"title": "QA Automation Intern", "company": "QualityNest", "location": "Remote", "job_type": "Internship", "salary": "₹7,000–₹12,000/month", "experience": "Fresher", "skills": ["Python", "Testing", "API", "Git", "Problem Solving"], "description": "Help write test cases, verify API responses, report reproducible bugs, and automate repeatable checks under the guidance of the QA team."},
    {"title": "SQL Support Associate", "company": "DataBridge Services", "location": "Chennai, Tamil Nadu", "job_type": "Full-time", "salary": "₹2.5–3.8 LPA", "experience": "Fresher", "skills": ["SQL", "MySQL", "Database", "Communication", "Problem Solving"], "description": "Assist with SQL queries, data checks, issue triage, and database documentation. Good fundamentals and clear communication are important."},
    {"title": "Junior API Developer", "company": "OrbitStack", "location": "Remote", "job_type": "Contract", "salary": "₹20,000–₹35,000/month", "experience": "0–1 year", "skills": ["Python", "FastAPI", "REST API", "Docker", "MongoDB"], "description": "Implement and document API endpoints, handle errors consistently, and collaborate on integration testing. This contract role is suitable for a project-driven beginner."},
    {"title": "Web Development Intern", "company": "NextStep Studio", "location": "Cuttack, Odisha", "job_type": "Internship", "salary": "₹5,000–₹10,000/month", "experience": "Fresher", "skills": ["HTML", "CSS", "JavaScript", "Bootstrap", "GitHub"], "description": "Build and maintain small web pages, improve mobile layouts, and learn version control through supervised project work."},
]

async def main():
    await client.admin.command("ping")
    await ensure_indexes()
    now = datetime.now(timezone.utc).isoformat()
    recruiter = await db.users.find_one({"email": DEMO_EMAIL})
    if not recruiter:
        recruiter_doc = {
            "name": "CareerPilot Demo Recruiter",
            "email": DEMO_EMAIL,
            "password_hash": hash_password(DEMO_PASSWORD),
            "role": "recruiter",
            "company": "CareerPilot Demo Network",
            "created_at": now,
            "is_demo_account": True,
        }
        result = await db.users.insert_one(recruiter_doc)
        recruiter_id = result.inserted_id
        print("Created demo recruiter account.")
    else:
        recruiter_id = recruiter["_id"]
        print("Using existing demo recruiter account.")

    admin_email = "admin@careerpilot.local"
    admin_password = "CareerPilotAdmin123!"
    admin = await db.users.find_one({"email": admin_email})
    if not admin:
        await db.users.insert_one({
            "name": "CareerPilot Administrator", "email": admin_email,
            "password_hash": hash_password(admin_password), "role": "admin",
            "company": "CareerPilot", "created_at": now, "is_demo_account": True
        })
        print("Created local demo admin account.")
    else:
        print("Using existing local demo admin account.")

    added = 0
    for job in JOBS:
        exists = await db.jobs.find_one({"title": job["title"], "company": job["company"], "is_demo_seed": True})
        if exists:
            continue
        document = {
            **job,
            "recruiter_id": recruiter_id,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "is_demo_seed": True,
        }
        await db.jobs.insert_one(document)
        added += 1

    print(f"MongoDB database: {db.name}")
    print(f"Demo jobs added this run: {added}; total seeded demo jobs: {await db.jobs.count_documents({'is_demo_seed': True})}")
    print("Demo recruiter login:")
    print(f"  Email: {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
    print("Demo admin login:")
    print(f"  Email: {admin_email}")
    print(f"  Password: {admin_password}")
    print("You can now start the API with: python -m uvicorn app.main:app --reload")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        client.close()
