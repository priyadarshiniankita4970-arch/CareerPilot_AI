from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str
    company: Optional[str] = Field(default=None, max_length=120)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    company: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=120)
    job_type: str = Field(default="Full-time", max_length=40)
    salary: str = Field(default="Not disclosed", max_length=80)
    experience: str = Field(default="Fresher", max_length=80)
    skills: List[str] = []
    description: str = Field(min_length=20, max_length=10000)

class ApplicationStatusIn(BaseModel):
    status: str
