"""
Database Schemas for Frontier Online Training Academy

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase of the class name (e.g., User -> "user").
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


# Core domain schemas
class User(BaseModel):
    name: str
    email: EmailStr
    role: Literal["student", "instructor", "admin"] = "student"
    avatar_url: Optional[str] = None


class Course(BaseModel):
    title: str
    category: Literal[
        "IELTS",
        "Accent & Spoken English",
        "Personality Development",
        "Leadership & Corporate Communication",
        "CPHQ & Healthcare Quality",
    ]
    description: str
    instructor: str
    level: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"
    tags: List[str] = []
    thumbnail_url: Optional[str] = None
    promo_video_url: Optional[str] = None
    price: float = 0.0


class Lesson(BaseModel):
    course_id: str
    title: str
    content_type: Literal["video", "pdf", "text"] = "video"
    video_url: Optional[str] = None
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    order: int = 0


class Quiz(BaseModel):
    course_id: str
    title: str
    questions: List[dict] = Field(
        default_factory=list,
        description="Array of questions: {question:str, options:[str], answer:int}",
    )


class Enrollment(BaseModel):
    user_id: str
    course_id: str
    status: Literal["enrolled", "completed"] = "enrolled"
    progress: float = 0.0  # 0-100


class Progress(BaseModel):
    user_id: str
    course_id: str
    completed_lessons: List[str] = []
    last_lesson_id: Optional[str] = None
    updated_at: Optional[datetime] = None


class Certificate(BaseModel):
    user_id: str
    course_id: str
    certificate_code: str
    issued_at: datetime
    url: Optional[str] = None


class NotificationToken(BaseModel):
    user_id: str
    provider: Literal["fcm", "apns"] = "fcm"
    device_token: str


class Payment(BaseModel):
    user_id: str
    course_id: str
    amount: float
    currency: Literal["USD", "INR"] = "USD"
    gateway: Literal["stripe", "razorpay"] = "stripe"
    status: Literal["created", "paid", "failed"] = "created"
    session_id: Optional[str] = None
