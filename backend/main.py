# =============================================================================
#  OSTADI — أستاذي
#  FastAPI Master Server Engine
#  Architect: Yacine Laguel
#  File: backend/main.py
# =============================================================================

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

# ---------------------------------------------------------------------------
# INTERNAL MODULE IMPORTS
# ---------------------------------------------------------------------------
from curriculum import (
    CURRICULUM_TREE,
    get_years_for_level,
    get_specialties_for_year,
    get_subjects_for_specialty,
)
from gemini_service import generate_exam_content
from pdf_exporter import build_exam_pdf, build_correction_pdf
from docx_exporter import build_exam_docx
from cleanup import schedule_file_deletion

# ---------------------------------------------------------------------------
# GEMINI API KEY — loaded from Render environment variable
# ---------------------------------------------------------------------------
import os as _os
GEMINI_API_KEY = _os.environ.get("GEMINI_API_KEY", "")

# ---------------------------------------------------------------------------
# LOGGING CONFIGURATION
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ostadi.main")

# ---------------------------------------------------------------------------
# CONSTANTS & PATH DECLARATIONS
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent
EXPORTS_DIR = BASE_DIR / "exports"
FONTS_DIR   = BASE_DIR / "fonts"

# Guarantee the ephemeral output directory always exists at startup
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# LIFESPAN CONTEXT MANAGER
# Runs startup and shutdown logic cleanly in FastAPI 0.95+
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: log server boot, verify font files exist, purge any stale
             export artefacts left from a previous crashed session.
    Shutdown: log graceful teardown.
    """
    log.info("═" * 70)
    log.info("  OSTADI SERVER — STARTING UP")
    log.info("═" * 70)

    # Verify Amiri font files are present — fail fast with a clear message
    required_fonts = ["Amiri-Regular.ttf", "Amiri-Bold.ttf"]
    for font_name in required_fonts:
        font_path = FONTS_DIR / font_name
        if not font_path.exists():
            log.error(
                f"CRITICAL: Font file missing → {font_path}\n"
                "Download from https://fonts.google.com/specimen/Amiri "
                "and place it in backend/fonts/"
            )
            raise FileNotFoundError(f"Required font not found: {font_path}")
        log.info(f"  ✔  Font verified: {font_name}")

    # Purge stale artefacts from the exports directory (previous crash remnants)
    purged = 0
    for stale_file in EXPORTS_DIR.iterdir():
        if stale_file.is_file():
            try:
                stale_file.unlink()
                purged += 1
            except OSError as exc:
                log.warning(f"Could not purge stale file {stale_file.name}: {exc}")
    if purged:
        log.info(f"  ✔  Purged {purged} stale artefact(s) from exports/")

    log.info("  ✔  Curriculum tree loaded successfully")
    log.info("  ✔  OSTADI is ready — http://127.0.0.1:8000")
    log.info("═" * 70)

    yield  # ←  application runs here

    log.info("═" * 70)
    log.info("  OSTADI SERVER — GRACEFUL SHUTDOWN")
    log.info("═" * 70)


# ---------------------------------------------------------------------------
# FASTAPI APPLICATION INSTANCE
# ---------------------------------------------------------------------------
app = FastAPI(
    title="أستاذي — Ostadi",
    description=(
        "نظام توليد الاختبارات الرسمية للمنظومة التربوية الجزائرية "
        "| Algerian National Education AI Exam Generator"
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS MIDDLEWARE
# Allows the local HTML frontend (file:// or live-server) to hit the API
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Locked down to localhost in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# STATIC FILE MOUNT
# Serves the frontend/index.html and any companion assets
# ---------------------------------------------------------------------------
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static_assets",
)

log.info(f"Frontend dir: {FRONTEND_DIR}")
log.info(f"Static dir: {STATIC_DIR}")


# =============================================================================
#  PYDANTIC REQUEST / RESPONSE SCHEMAS
# =============================================================================

class CurriculumQueryRequest(BaseModel):
    """
    Used by the cascading dropdown endpoints.
    The frontend sends the currently selected value to receive
    the next valid set of options.
    """
    level: Optional[str] = Field(
        None,
        description="Educational tier: PRIMARY | MIDDLE | HIGH",
        example="HIGH",
    )
    year: Optional[str] = Field(
        None,
        description="Academic year code, e.g. 1AS, 3AM, 5AP",
        example="2AS",
    )
    specialty: Optional[str] = Field(
        None,
        description="Specialty / stream identifier",
        example="علوم تجريبية",
    )


class ExamGenerationRequest(BaseModel):
    """
    The complete parameter payload submitted when the teacher
    clicks 'توليد الاختبار' (Generate Exam).
    """
    educational_level: str = Field(
        ...,
        description="PRIMARY / MIDDLE / HIGH",
        example="HIGH",
    )
    academic_year: str = Field(
        ...,
        description="e.g. 2AS, 4AM, 5AP",
        example="2AS",
    )
    specialty_stream: str = Field(
        ...,
        description="The specialty or stream label",
        example="علوم تجريبية",
    )
    subject: str = Field(
        ...,
        description="The target subject",
        example="العلوم الفيزيائية والتكنولوجيا",
    )
    trimester: str = Field(
        ...,
        description="الفصل الأول | الفصل الثاني | الفصل الثالث",
        example="الفصل الأول",
    )
    duration: int = Field(
        ...,
        ge=30,
        le=180,
        description="Exam duration in minutes",
        example=60,
    )
    difficulty: str = Field(
        ...,
        description="سهل | متوسط | صعب",
        example="متوسط",
    )
    @validator("trimester")
    def validate_trimester(cls, v: str) -> str:
        allowed = {"الفصل الأول", "الفصل الثاني", "الفصل الثالث"}
        if v not in allowed:
            raise ValueError(f"trimester must be one of {allowed}")
        return v

    @validator("difficulty")
    def validate_difficulty(cls, v: str) -> str:
        allowed = {"سهل", "متوسط", "صعب"}
        if v not in allowed:
            raise ValueError(f"difficulty must be one of {allowed}")
        return v


class ExamGenerationResponse(BaseModel):
    """
    Returned to the frontend after a successful generation cycle.
    Contains pre-signed relative download URLs for each artefact.
    """
    session_id: str
    exam_pdf_url: str
    correction_pdf_url: str
    exam_docx_url: str
    expires_in_minutes: int = 30
    subject: str
    academic_year: str
    trimester: str


# =============================================================================
#  CURRICULUM CASCADE ENDPOINTS
#  The frontend calls these three endpoints in sequence to build
#  the dependent dropdown hierarchy without page reloads.
# =============================================================================

@app.get(
    "/api/curriculum/levels",
    summary="Get all educational levels",
    tags=["Curriculum Cascade"],
)
async def get_levels() -> JSONResponse:
    """
    Returns the three top-level tiers of the Algerian education system.
    This is the first dropdown the teacher sees.
    """
    levels = [
        {"id": "PRIMARY",  "label": "الطور الابتدائي",          "sub": "1AP → 5AP"},
        {"id": "MIDDLE",   "label": "الطور المتوسط (CEM)",       "sub": "1AM → 4AM"},
        {"id": "HIGH",     "label": "الطور الثانوي (Lycée)",     "sub": "1AS → 3AS"},
    ]
    return JSONResponse(content={"levels": levels})


@app.get(
    "/api/curriculum/years/{level}",
    summary="Get academic years for a given level",
    tags=["Curriculum Cascade"],
)
async def get_years(level: str) -> JSONResponse:
    """
    Given a level ID (PRIMARY | MIDDLE | HIGH), returns the list
    of valid academic year codes for that tier.
    """
    years = get_years_for_level(level.upper())
    if years is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown educational level: '{level}'. "
                   f"Valid options are PRIMARY, MIDDLE, HIGH.",
        )
    return JSONResponse(content={"years": years})


@app.get(
    "/api/curriculum/specialties/{level}/{year}",
    summary="Get specialties / streams for a given year",
    tags=["Curriculum Cascade"],
)
async def get_specialties(level: str, year: str) -> JSONResponse:
    """
    Returns the list of specialties available for a specific
    level + year combination. For PRIMARY and MIDDLE levels,
    this returns a single 'General Track' entry.
    """
    specialties = get_specialties_for_year(level.upper(), year)
    if specialties is None:
        raise HTTPException(
            status_code=404,
            detail=f"No specialty data found for level='{level}' year='{year}'.",
        )
    return JSONResponse(content={"specialties": specialties})


@app.get(
    "/api/curriculum/subjects/{level}/{year}/{specialty}",
    summary="Get subjects for a given specialty",
    tags=["Curriculum Cascade"],
)
async def get_subjects(level: str, year: str, specialty: str) -> JSONResponse:
    """
    Final cascade step. Returns the list of subjects taught in
    the specified level / year / specialty combination.
    """
    subjects = get_subjects_for_specialty(level.upper(), year, specialty)
    if subjects is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No subject data found for "
                f"level='{level}' / year='{year}' / specialty='{specialty}'."
            ),
        )
    return JSONResponse(content={"subjects": subjects})


# =============================================================================
#  CORE GENERATION ENDPOINT
#  The heart of the application. Orchestrates:
#    1. Gemini content generation
#    2. PDF compilation (exam + correction)
#    3. DOCX compilation
#    4. 30-minute ephemeral deletion scheduling
# =============================================================================

@app.post(
    "/api/generate",
    response_model=ExamGenerationResponse,
    summary="Generate a full exam package",
    tags=["Exam Generation"],
)
async def generate_exam(
    request: ExamGenerationRequest,
    background_tasks: BackgroundTasks,
) -> ExamGenerationResponse:
    """
    Master generation pipeline:

    Step 1 → Call Gemini API with the structured pedagogical prompt.
             Retry automatically on HTTP 429 with exponential backoff.
    Step 2 → Parse the returned JSON payload (exam body + correction key).
    Step 3 → Compile the official-format Arabic RTL exam PDF.
    Step 4 → Compile the official correction + grading scale PDF.
    Step 5 → Compile the editable DOCX artefact.
    Step 6 → Register all three files for automatic deletion in 30 minutes.
    Step 7 → Return the download URLs to the frontend.
    """
    session_id = str(uuid.uuid4()).replace("-", "")[:16].upper()
    log.info(f"[{session_id}] Generation request received — {request.academic_year} / {request.subject}")

    # ------------------------------------------------------------------
    # STEP 1 & 2: GEMINI GENERATION
    # ------------------------------------------------------------------
    try:
        raw_json_payload: Dict[str, Any] = await generate_exam_content(
            api_key=GEMINI_API_KEY,
            educational_level=request.educational_level,
            academic_year=request.academic_year,
            specialty_stream=request.specialty_stream,
            subject=request.subject,
            trimester=request.trimester,
            duration=request.duration,
            difficulty=request.difficulty,
            session_id=session_id,
        )
    except ValueError as exc:
        log.error(f"[{session_id}] Gemini returned invalid JSON: {exc}")
        raise HTTPException(
            status_code=422,
            detail=(
                "فشل تحليل مخرجات الذكاء الاصطناعي — "
                "The AI returned a malformed response. Please retry."
            ),
        )
    except RuntimeError as exc:
        log.error(f"[{session_id}] Gemini API failure after retries: {exc}")
        raise HTTPException(
            status_code=503,
            detail=(
                "تعذّر الاتصال بخدمة الذكاء الاصطناعي بعد محاولات متعددة — "
                f"Gemini API error: {exc}"
            ),
        )

    log.info(f"[{session_id}] ✔ Gemini payload received and parsed")

    # ------------------------------------------------------------------
    # STEP 3: BUILD EXAM PDF
    # ------------------------------------------------------------------
    exam_pdf_filename  = f"ostadi_exam_{session_id}.pdf"
    exam_pdf_path      = EXPORTS_DIR / exam_pdf_filename

    try:
        build_exam_pdf(
            output_path=exam_pdf_path,
            payload=raw_json_payload,
            academic_year=request.academic_year,
            specialty_stream=request.specialty_stream,
            subject=request.subject,
            trimester=request.trimester,
            duration=request.duration,
            fonts_dir=FONTS_DIR,
        )
    except Exception as exc:
        log.error(f"[{session_id}] PDF (exam) compilation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation error: {exc}")

    log.info(f"[{session_id}] ✔ Exam PDF compiled → {exam_pdf_filename}")

    # ------------------------------------------------------------------
    # STEP 4: BUILD CORRECTION PDF
    # ------------------------------------------------------------------
    correction_pdf_filename = f"ostadi_correction_{session_id}.pdf"
    correction_pdf_path     = EXPORTS_DIR / correction_pdf_filename

    try:
        build_correction_pdf(
            output_path=correction_pdf_path,
            payload=raw_json_payload,
            academic_year=request.academic_year,
            specialty_stream=request.specialty_stream,
            subject=request.subject,
            trimester=request.trimester,
            fonts_dir=FONTS_DIR,
        )
    except Exception as exc:
        log.error(f"[{session_id}] PDF (correction) compilation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Correction PDF error: {exc}")

    log.info(f"[{session_id}] ✔ Correction PDF compiled → {correction_pdf_filename}")

    # ------------------------------------------------------------------
    # STEP 5: BUILD EDITABLE DOCX
    # ------------------------------------------------------------------
    exam_docx_filename = f"ostadi_exam_{session_id}.docx"
    exam_docx_path     = EXPORTS_DIR / exam_docx_filename

    try:
        build_exam_docx(
            output_path=exam_docx_path,
            payload=raw_json_payload,
            academic_year=request.academic_year,
            specialty_stream=request.specialty_stream,
            subject=request.subject,
            trimester=request.trimester,
            duration=request.duration,
            fonts_dir=FONTS_DIR,
        )
    except Exception as exc:
        log.error(f"[{session_id}] DOCX compilation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DOCX generation error: {exc}")

    log.info(f"[{session_id}] ✔ Exam DOCX compiled → {exam_docx_filename}")

    # ------------------------------------------------------------------
    # STEP 6: SCHEDULE EPHEMERAL DELETION (30 minutes)
    # ------------------------------------------------------------------
    files_to_delete = [exam_pdf_path, correction_pdf_path, exam_docx_path]
    background_tasks.add_task(
        schedule_file_deletion,
        file_paths=files_to_delete,
        delay_seconds=1800,        # 30 minutes exactly
        session_id=session_id,
    )
    log.info(f"[{session_id}] ✔ Ephemeral deletion scheduled in 30 minutes")

    # ------------------------------------------------------------------
    # STEP 7: RETURN DOWNLOAD URLS
    # ------------------------------------------------------------------
    return ExamGenerationResponse(
        session_id=session_id,
        exam_pdf_url=f"/api/download/{exam_pdf_filename}",
        correction_pdf_url=f"/api/download/{correction_pdf_filename}",
        exam_docx_url=f"/api/download/{exam_docx_filename}",
        expires_in_minutes=30,
        subject=request.subject,
        academic_year=request.academic_year,
        trimester=request.trimester,
    )


# =============================================================================
#  DOWNLOAD ENDPOINT
#  Serves the generated files as HTTP attachments.
#  Validates that the requested filename lives inside the exports directory
#  to prevent path traversal attacks.
# =============================================================================

@app.get(
    "/api/download/{filename}",
    summary="Download a generated exam artefact",
    tags=["Downloads"],
)
async def download_file(filename: str) -> FileResponse:
    """
    Serves a generated PDF or DOCX file.
    The file is validated against the exports directory before serving.
    Returns HTTP 404 if the file has already been auto-deleted
    (i.e., the 30-minute window has elapsed).
    """
    # Security: resolve the full path and verify it is inside EXPORTS_DIR
    requested_path = (EXPORTS_DIR / filename).resolve()

    if not str(requested_path).startswith(str(EXPORTS_DIR.resolve())):
        log.warning(f"Path traversal attempt blocked: {filename}")
        raise HTTPException(status_code=403, detail="Access denied.")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "الملف غير متوفر — انتهت صلاحية التحميل (30 دقيقة). "
                "يرجى توليد الاختبار من جديد. | "
                "File not found — the 30-minute download window has expired."
            ),
        )

    # Determine correct media type from extension
    suffix = requested_path.suffix.lower()
    media_type_map = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument"
                 ".wordprocessingml.document",
    }
    media_type = media_type_map.get(suffix, "application/octet-stream")

    log.info(f"Serving download: {filename}")
    return FileResponse(
        path=str(requested_path),
        media_type=media_type,
        filename=filename,
    )


# =============================================================================
#  HEALTH CHECK ENDPOINT
#  Used by the frontend to verify the server is alive before the teacher
#  clicks generate.
# =============================================================================

@app.get(
    "/api/health",
    summary="Server health check",
    tags=["System"],
)
async def health_check() -> JSONResponse:
    exports_count = sum(1 for f in EXPORTS_DIR.iterdir() if f.is_file())
    return JSONResponse(content={
        "status": "ok",
        "service": "Ostadi — أستاذي",
        "version": "1.0.0",
        "exports_pending": exports_count,
    })


# =============================================================================
#  ROOT ROUTE — SERVES THE FRONTEND INDEX PAGE
# =============================================================================

from fastapi.responses import HTMLResponse

@app.get("/", include_in_schema=False)
async def serve_frontend() -> HTMLResponse:
    # Try file first, fallback to embedded HTML
    index_path = BASE_DIR / "frontend" / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    index_path2 = BASE_DIR.parent / "frontend" / "index.html"
    if index_path2.exists():
        return HTMLResponse(content=index_path2.read_text(encoding="utf-8"))
    raise HTTPException(status_code=503, detail="Frontend not found.")


# =============================================================================
#  GLOBAL EXCEPTION HANDLER
#  Catches any unhandled exception and returns a clean Arabic+English
#  error message instead of a raw Python traceback.
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "حدث خطأ داخلي في الخادم — "
                "An internal server error occurred. Please contact support."
            ),
            "path": str(request.url.path),
        },
    )


# =============================================================================
#  ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
        log_level="info",
    )
