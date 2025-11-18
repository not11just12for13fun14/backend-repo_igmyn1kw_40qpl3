import os
import random
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents

app = FastAPI(title="Frontier Online Training Academy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Utility ---

def collection(name: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    return db[name]


# --- Models for requests ---
class CreateUser(BaseModel):
    name: str
    email: str
    role: str = "student"


class CreateCourse(BaseModel):
    title: str
    category: str
    description: str
    instructor: str
    level: str = "Beginner"
    tags: List[str] = []
    price: float = 0.0
    thumbnail_url: Optional[str] = None
    promo_video_url: Optional[str] = None


class CreateLesson(BaseModel):
    course_id: str
    title: str
    content_type: str = "video"
    video_url: Optional[str] = None
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    order: int = 0


class CreateQuiz(BaseModel):
    course_id: str
    title: str
    questions: List[dict] = []


class QuizSubmission(BaseModel):
    quiz_id: str
    answers: List[int]


class EnrollmentReq(BaseModel):
    user_id: str
    course_id: str


class ProgressUpdate(BaseModel):
    user_id: str
    course_id: str
    lesson_id: str


class PaymentInit(BaseModel):
    user_id: str
    course_id: str
    gateway: str = "stripe"  # or razorpay
    currency: str = "USD"


# --- Seed data (idempotent) ---
@app.on_event("startup")
def seed_data():
    if db is None:
        return

    if collection("course").count_documents({}) == 0:
        sample_courses = [
            {
                "title": "IELTS Mastery Program",
                "category": "IELTS",
                "description": "Comprehensive IELTS prep with practice tests and feedback.",
                "instructor": "Dr. Aisha Khan",
                "level": "Intermediate",
                "tags": ["IELTS", "Exam"],
                "price": 149.0,
                "thumbnail_url": "https://images.unsplash.com/photo-1523580846011-d3a5bc25702b",
            },
            {
                "title": "British Accent & Spoken English",
                "category": "Accent & Spoken English",
                "description": "Refine pronunciation, rhythm and intonation with native patterns.",
                "instructor": "James Parker",
                "level": "Beginner",
                "tags": ["Accent", "Speaking"],
                "price": 129.0,
                "thumbnail_url": "https://images.unsplash.com/photo-1529078155058-5d716f45d604",
            },
            {
                "title": "Personality Development & Soft Skills",
                "category": "Personality Development",
                "description": "Boost confidence, presence and workplace communication.",
                "instructor": "Neha Sharma",
                "level": "Beginner",
                "tags": ["Soft Skills", "Confidence"],
                "price": 99.0,
                "thumbnail_url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c",
            },
            {
                "title": "Leadership & Corporate Communication",
                "category": "Leadership & Corporate Communication",
                "description": "Lead with clarity: executive presence, influence and storytelling.",
                "instructor": "Rahul Verma",
                "level": "Advanced",
                "tags": ["Leadership", "Corporate"],
                "price": 199.0,
                "thumbnail_url": "https://images.unsplash.com/photo-1521791136064-7986c2920216",
            },
            {
                "title": "CPHQ & Healthcare Quality Training",
                "category": "CPHQ & Healthcare Quality",
                "description": "Prepare for CPHQ with quality frameworks, patient safety and analytics.",
                "instructor": "Dr. Sara Malik",
                "level": "Advanced",
                "tags": ["CPHQ", "Healthcare"],
                "price": 249.0,
                "thumbnail_url": "https://images.unsplash.com/photo-1584982751687-51f29c073f0f",
            },
        ]
        for c in sample_courses:
            create_document("course", c)


# --- Health ---
@app.get("/")
async def root():
    return {"name": "Frontier Online Training Academy API", "status": "ok"}


@app.get("/test")
async def test_database():
    resp = {
        "backend": "ok",
        "database": "not available" if db is None else "connected",
        "collections": [],
    }
    if db is not None:
        resp["collections"] = db.list_collection_names()
    return resp


# --- Public endpoints ---
@app.get("/api/courses")
async def list_courses(category: Optional[str] = None, q: Optional[str] = None):
    filt = {}
    if category:
        filt["category"] = category
    if q:
        filt["title"] = {"$regex": q, "$options": "i"}
    return get_documents("course", filt, limit=100)


@app.get("/api/courses/{course_id}")
async def course_detail(course_id: str):
    doc = collection("course").find_one({"_id": {"$oid": course_id}}) or collection("course").find_one({"_id": course_id})
    if not doc:
        raise HTTPException(404, "Course not found")
    return doc


@app.post("/api/enroll")
async def enroll(enr: EnrollmentReq):
    # ensure not duplicate
    existing = collection("enrollment").find_one({"user_id": enr.user_id, "course_id": enr.course_id})
    if existing:
        return existing
    _id = create_document("enrollment", {"user_id": enr.user_id, "course_id": enr.course_id, "status": "enrolled", "progress": 0.0})
    return {"_id": _id, "status": "enrolled"}


@app.get("/api/lessons/{course_id}")
async def lessons(course_id: str):
    return get_documents("lesson", {"course_id": course_id}, limit=200)


@app.post("/api/progress")
async def mark_progress(p: ProgressUpdate):
    pr = collection("progress").find_one({"user_id": p.user_id, "course_id": p.course_id})
    completed = set(pr.get("completed_lessons", [])) if pr else set()
    completed.add(p.lesson_id)
    data = {
        "user_id": p.user_id,
        "course_id": p.course_id,
        "completed_lessons": list(completed),
        "last_lesson_id": p.lesson_id,
        "updated_at": datetime.utcnow(),
    }
    if pr:
        collection("progress").update_one({"_id": pr["_id"]}, {"$set": data})
    else:
        create_document("progress", data)
    # compute percent
    total_lessons = collection("lesson").count_documents({"course_id": p.course_id}) or 1
    percent = round(100 * len(completed) / total_lessons, 2)
    collection("enrollment").update_one({"user_id": p.user_id, "course_id": p.course_id}, {"$set": {"progress": percent}} , upsert=True)
    return {"progress": percent}


# --- Quizzes ---
@app.get("/api/quizzes/{course_id}")
async def get_quiz(course_id: str):
    qz = collection("quiz").find_one({"course_id": course_id})
    if not qz:
        # seed a simple quiz
        qz_id = create_document(
            "quiz",
            {
                "course_id": course_id,
                "title": "Quick Check",
                "questions": [
                    {"question": "Effective communication is primarily about?", "options": ["Speaking", "Listening", "Grammar", "Accent"], "answer": 1},
                    {"question": "IELTS stands for?", "options": ["International English Language Testing System", "Indian English Language Test Suite", "Integrated ELT System", "None"], "answer": 0},
                ],
            },
        )
        qz = collection("quiz").find_one({"_id": qz_id}) or collection("quiz").find_one({"course_id": course_id})
    return qz


@app.post("/api/quizzes/submit")
async def submit_quiz(payload: QuizSubmission):
    qz = collection("quiz").find_one({"_id": payload.quiz_id}) or collection("quiz").find_one({"_id": {"$oid": payload.quiz_id}})
    if not qz:
        raise HTTPException(404, "Quiz not found")
    correct = 0
    for idx, q in enumerate(qz.get("questions", [])):
        if idx < len(payload.answers) and payload.answers[idx] == q.get("answer"):
            correct += 1
    score = round(100 * correct / max(1, len(qz.get("questions", []))), 2)
    result = {"quiz_id": str(qz.get("_id")), "score": score}
    return result


# --- Certificates ---
@app.post("/api/certificates/issue")
async def issue_certificate(user_id: str, course_id: str):
    code = f"FO-{random.randint(100000, 999999)}"
    existing = collection("certificate").find_one({"user_id": user_id, "course_id": course_id})
    if existing:
        return existing
    _id = create_document(
        "certificate",
        {
            "user_id": user_id,
            "course_id": course_id,
            "certificate_code": code,
            "issued_at": datetime.utcnow(),
            "url": f"https://certs.frontier.example/{code}",
        },
    )
    return {"_id": _id, "certificate_code": code}


# --- Payments (mock create checkout session) ---
@app.post("/api/payments/create-session")
async def create_payment_session(req: PaymentInit):
    # In production: integrate with Stripe/Razorpay SDKs, webhooks, etc.
    session_id = f"sess_{random.randint(100000,999999)}"
    _id = create_document(
        "payment",
        {
            "user_id": req.user_id,
            "course_id": req.course_id,
            "amount": float(collection("course").find_one({"_id": {"$oid": req.course_id}}) or {}).get("price", 0.0),
            "currency": req.currency,
            "gateway": req.gateway,
            "status": "created",
            "session_id": session_id,
        },
    )
    return {"session_id": session_id, "payment_id": _id}


# --- Admin endpoints (basic) ---
@app.post("/api/admin/courses")
async def admin_create_course(payload: CreateCourse):
    _id = create_document("course", payload.model_dump())
    return {"_id": _id}


@app.post("/api/admin/lessons")
async def admin_create_lesson(payload: CreateLesson):
    _id = create_document("lesson", payload.model_dump())
    return {"_id": _id}


@app.post("/api/admin/quizzes")
async def admin_create_quiz(payload: CreateQuiz):
    _id = create_document("quiz", payload.model_dump())
    return {"_id": _id}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
