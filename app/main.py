from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.batches import router as batches_router
from app.api.exams import router as exams_router
from app.api.questions import router as questions_router
from app.api.exam_attempts import router as exam_attempts_router
from app.api.student_exams import router as student_exams_router

app = FastAPI(
    title="ExamForge API",
    swagger_ui_parameters={
        "persistAuthorization": True
    },
    description="AI-Powered Online Examination & Assessment Platform",
    version="1.0.0",
)


app.include_router(auth_router)
app.include_router(batches_router)
app.include_router(exams_router)
app.include_router(questions_router)
app.include_router(exam_attempts_router)
app.include_router(student_exams_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ExamForge API"
    }
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://examforge-frountend.vercel.app/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)