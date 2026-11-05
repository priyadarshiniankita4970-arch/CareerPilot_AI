import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "careerpilot")

client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
db = client[DATABASE_NAME]

async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.jobs.create_index([("title", "text"), ("company", "text"), ("description", "text"), ("location", "text")])
    await db.applications.create_index([("job_id", 1), ("student_id", 1)], unique=True)
    await db.applications.create_index("student_id")
    await db.saved_jobs.create_index([("student_id", 1), ("job_id", 1)], unique=True)
    await db.saved_jobs.create_index("student_id")
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.resume_profiles.create_index("user_id", unique=True)
    await db.roadmap_progress.create_index([("user_id", 1), ("title", 1)], unique=True)
    await db.interview_attempts.create_index([("user_id", 1), ("created_at", -1)])
