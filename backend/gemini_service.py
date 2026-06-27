# =============================================================================
#  OSTADI — أستاذي
#  Gemini API Service Engine
#  Architect: Yacine Laguel
#  File: backend/gemini_service.py
#
#  Responsibilities:
#    1. Build the full Ministry-grade Arabic system prompt dynamically
#       from the exam parameters passed by main.py
#    2. Call the Gemini 1.5 Flash API with full error handling
#    3. Implement exponential backoff retry on HTTP 429 (quota exceeded)
#    4. Parse and validate the JSON payload returned by Gemini
#    5. Return a clean structured Python dict to main.py
#
#  The returned dict is consumed by:
#    - pdf_exporter.py  (exam PDF + correction PDF)
#    - docx_exporter.py (editable DOCX)
# =============================================================================

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from curriculum import get_subject_type, get_full_year_label, validate_exam_parameters

# ---------------------------------------------------------------------------
# MODULE LOGGER
# ---------------------------------------------------------------------------
log = logging.getLogger("ostadi.gemini")

# ---------------------------------------------------------------------------
# RETRY POLICY CONSTANTS
# ---------------------------------------------------------------------------
MAX_RETRY_ATTEMPTS   = 6      # Maximum number of attempts before giving up
BASE_BACKOFF_SECONDS = 2.0    # Initial wait time on first retry
BACKOFF_MULTIPLIER   = 2.0    # Each retry doubles the wait
MAX_BACKOFF_SECONDS  = 64.0   # Hard ceiling on wait time between retries
JITTER_RANGE         = 1.0    # ±1 second random jitter to prevent thundering herd

# ---------------------------------------------------------------------------
# GEMINI MODEL CONFIGURATION
# ---------------------------------------------------------------------------
GEMINI_MODEL_NAME = "gemini-2.0-flash-lite"
GEMINI_MAX_TOKENS    = 8192   # Maximum output tokens — exams can be long
GEMINI_TEMPERATURE   = 0.4    # Low temp → deterministic, structured output
GEMINI_TOP_P         = 0.9
GEMINI_TOP_K         = 40


# =============================================================================
#  SECTION 1: SYSTEM PROMPT BUILDER
#  Constructs the complete Arabic Ministry-grade pedagogical instruction
#  block that is injected as the system instruction into Gemini.
# =============================================================================

def _build_system_prompt(subject_type: str) -> str:
    """
    Returns the static system-level instruction that defines Gemini's
    persona and the absolute pedagogical constraints it must obey.

    subject_type: 'LITERARY' or 'SCIENTIFIC'
    """

    if subject_type == "LITERARY":
        structure_instructions = """
هيكلية ورقة الاختبار للمواد الأدبية واللغوية:
يجب صياغة سند/نص أدبي أو علمي بليغ ومناسب للبيئة الجزائرية والقيم الوطنية، يليه أسئلة مقسمة إلى الأجزاء الثلاثة الآتية بدقة تامة:
  - الجزء الأول — البناء الفكري (6 نقاط):
    أسئلة تقيس الفهم والاستيعاب والتحليل العميق للنص، موزعة على 4 إلى 6 أسئلة فرعية متدرجة.
  - الجزء الثاني — البناء اللغوي (6 نقاط):
    أسئلة تتناول القواعد النحوية والصرفية والبلاغية المرتبطة بالنص، موزعة على 4 إلى 6 أسئلة فرعية.
  - الجزء الثالث — الوضعية الإدماجية (8 نقاط):
    وضعية إدماجية سياقية واضحة تطلب من التلميذ إنتاج نص كتابي مرتبط بمحور الدرس، مع شبكة تقويم مؤشرية تفصيلية تشمل: المؤشر، المعيار، العلامة المخصصة.
"""
    else:
        structure_instructions = """
هيكلية ورقة الاختبار للمواد العلمية والتقنية:
يجب تقسيم الورقة إلى تمارين مستقلة ومتدرجة في الصعوبة كالآتي:
  - التمرين الأول (6 نقاط):
    تمرين تطبيقي مباشر يقيس استيعاب المفاهيم الأساسية للدرس.
  - التمرين الثاني (6 نقاط):
    تمرين متوسط الصعوبة يدمج مفهومين أو أكثر من دروس الفصل.
  - المسألة الإدماجية المركبة (8 نقاط):
    مسألة شاملة تجمع مفاهيم متعددة في سياق واقعي تطبيقي، مع بيانات كاملة وأسئلة فرعية متسلسلة.
"""

    return f"""أنت مفتش التربية الوطنية في الجمهورية الجزائرية الديمقراطية الشعبية.
مهمتك المطلقة والوحيدة هي توليد موضوع اختبار رسمي مطابق تماماً للمقاييس البيداغوجية للوزارة، مرفقاً بتصحيح نموذجي كامل وسلّم تنقيط تفصيلي.

القيود البيداغوجية الصارمة والمطلقة:
1. الالتزام الحرفي بالمخطط السنوي: يُحظر بشكل قاطع صياغة أي سؤال أو استخدام أي مصطلح لا ينتمي إلى الدروس المقررة رسمياً من الوزارة لهذا الفصل بعينه. يجب أن تتطابق التعاريف والمفاهيم مع الكتاب المدرسي الجزائري الرسمي.
2. لغة الإخراج: اللغة العربية الفصحى السليمة في جميع أجزاء الموضوع والتصحيح دون استثناء، باستثناء المواد التي لغتها الفرنسية أو الإنجليزية فتكون بلغتها الأصلية.
3. دقة التنقيط: يجب أن يكون مجموع علامات الاختبار 20 نقطة بالضبط. يُسمح باستخدام الكسور الدقيقة مثل 0.25 ن و0.5 ن و0.75 ن و1.25 ن لضمان التوزيع الصحيح.

{structure_instructions}

التصحيح النموذجي وسلّم التنقيط:
يجب إنتاج ملحق منفصل تحت عنوان "التصحيح النموذجي وسلّم التنقيط الرسمي" يحتوي على:
  - إجابة نموذجية دقيقة ومفصلة لكل جزئية من جزئيات الاختبار.
  - العلامة المخصصة لكل جزئية بدقة عشرية إن اقتضى الأمر.
  - المجموع الكلي 20/20 في نهاية سلّم التنقيط.

صيغة الإخراج الحتمية:
يجب أن تُعيد مخرجاتك كاملةً في قالب JSON صالح تقنياً، بدون أي نص خارج القالب، بدون علامات markdown، بدون كتلة ```json```. النموذج المطلوب هو:

{{
  "exam": {{
    "title": "موضوع الاختبار",
    "text_passage": "النص الكامل أو null للمواد العلمية",
    "sections": [
      {{
        "section_title": "عنوان الجزء",
        "points_total": 6,
        "questions": [
          {{
            "number": "1",
            "text": "نص السؤال الكامل",
            "sub_questions": [
              {{
                "number": "أ",
                "text": "نص السؤال الفرعي",
                "points": 1.5
              }}
            ],
            "points": null
          }}
        ]
      }}
    ],
    "integration_grid": null
  }},
  "correction": {{
    "title": "التصحيح النموذجي وسلّم التنقيط الرسمي",
    "sections": [
      {{
        "section_title": "عنوان الجزء",
        "answers": [
          {{
            "question_number": "1",
            "sub_question_number": "أ",
            "answer_text": "الإجابة النموذجية الكاملة",
            "points": 1.5
          }}
        ]
      }}
    ],
    "total_points": 20
  }}
}}"""


def _build_user_prompt(
    educational_level: str,
    academic_year: str,
    specialty_stream: str,
    subject: str,
    trimester: str,
    duration: int,
    difficulty: str,
    year_label_ar: str,
) -> str:
    """
    Builds the user-turn message that contains all the dynamic
    exam parameters. This is sent as the 'user' role message
    alongside the system instruction.
    """

    difficulty_descriptors = {
        "سهل":   "مستوى سهل: الأسئلة مباشرة وتقيس التذكر والفهم البسيط فقط.",
        "متوسط": "مستوى متوسط: الأسئلة تجمع بين الفهم والتطبيق بتوازن دقيق.",
        "صعب":   "مستوى صعب: الأسئلة تتطلب تحليلاً عميقاً ودمجاً للمفاهيم وإبداعاً في الحل.",
    }

    difficulty_desc = difficulty_descriptors.get(difficulty, difficulty_descriptors["متوسط"])

    return f"""قم بتوليد موضوع الاختبار الرسمي وفق المعطيات الدقيقة التالية:

══════════════════════════════════════════
  معطيات الاختبار الرسمية
══════════════════════════════════════════
  الطور التعليمي   :  {educational_level}
  السنة الدراسية  :  {year_label_ar} ({academic_year})
  الشعبة / التخصص :  {specialty_stream}
  المادة المستهدفة :  {subject}
  الفترة           :  {trimester}
  مدة الاختبار     :  {duration} دقيقة
  درجة الصعوبة    :  {difficulty_desc}
══════════════════════════════════════════

التزم بشكل مطلق بالمخطط السنوي الرسمي لهذا الفصل.
أعد مخرجاتك في قالب JSON النقي الموصوف في تعليمات النظام فقط، دون أي نص إضافي."""


# =============================================================================
#  SECTION 2: EXPONENTIAL BACKOFF RETRY ENGINE
# =============================================================================

async def _call_gemini_with_backoff(
    model: genai.GenerativeModel,
    user_prompt: str,
    session_id: str,
) -> str:
    """
    Calls the Gemini API and retries automatically on quota (429) or
    service unavailability (503) errors using exponential backoff with jitter.

    Returns the raw text response string from Gemini on success.
    Raises RuntimeError after MAX_RETRY_ATTEMPTS consecutive failures.
    """
    import random

    attempt = 0
    last_exception = None

    while attempt < MAX_RETRY_ATTEMPTS:
        attempt += 1
        log.info(f"[{session_id}] Gemini API call — attempt {attempt}/{MAX_RETRY_ATTEMPTS}")

        try:
            # Gemini's Python SDK generate_content is synchronous.
            # We run it in an executor to avoid blocking the event loop.
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(user_prompt),
            )

            # Validate the response object
            if not response or not response.text:
                raise ValueError("Gemini returned an empty response object.")

            log.info(
                f"[{session_id}] ✔ Gemini responded — "
                f"{len(response.text)} characters received"
            )
            return response.text

        except ResourceExhausted as exc:
            # HTTP 429 — quota exceeded
            last_exception = exc
            wait_time = min(
                BASE_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1)),
                MAX_BACKOFF_SECONDS,
            )
            jitter = random.uniform(-JITTER_RANGE, JITTER_RANGE)
            total_wait = max(0.5, wait_time + jitter)

            log.warning(
                f"[{session_id}] ⚠ Quota exceeded (429) — "
                f"waiting {total_wait:.1f}s before retry {attempt + 1}..."
            )
            await asyncio.sleep(total_wait)

        except ServiceUnavailable as exc:
            # HTTP 503 — Gemini temporarily unavailable
            last_exception = exc
            wait_time = min(
                BASE_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1)),
                MAX_BACKOFF_SECONDS,
            )
            jitter = random.uniform(0, JITTER_RANGE)
            total_wait = wait_time + jitter

            log.warning(
                f"[{session_id}] ⚠ Service unavailable (503) — "
                f"waiting {total_wait:.1f}s before retry {attempt + 1}..."
            )
            await asyncio.sleep(total_wait)

        except Exception as exc:
            # Any other exception is non-retriable — fail immediately
            log.error(
                f"[{session_id}] ✖ Non-retriable Gemini error on attempt {attempt}: {exc}",
                exc_info=True,
            )
            raise RuntimeError(
                f"Gemini API call failed with a non-retriable error: {exc}"
            ) from exc

    # All retries exhausted
    raise RuntimeError(
        f"Gemini API call failed after {MAX_RETRY_ATTEMPTS} attempts. "
        f"Last error: {last_exception}"
    )


# =============================================================================
#  SECTION 3: JSON RESPONSE PARSER & VALIDATOR
# =============================================================================

def _parse_and_validate_gemini_response(
    raw_text: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Parses the raw text returned by Gemini into a validated Python dict.

    Gemini occasionally wraps JSON in markdown fences (```json ... ```)
    despite instructions. This function strips any such wrapping before
    attempting JSON parsing.

    Validates that the returned structure contains the required top-level
    keys ('exam' and 'correction') and that the correction total is 20.

    Raises ValueError with a descriptive message on any structural failure.
    """

    # ---- Strip markdown fences if present ----
    cleaned = raw_text.strip()

    # Pattern: ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
    match = fence_pattern.match(cleaned)
    if match:
        cleaned = match.group(1).strip()
        log.debug(f"[{session_id}] Stripped markdown fences from Gemini response")

    # ---- Attempt JSON parse ----
    try:
        payload: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.error(
            f"[{session_id}] JSON decode failed.\n"
            f"Raw text preview (first 500 chars):\n{raw_text[:500]}"
        )
        raise ValueError(
            f"Gemini response is not valid JSON: {exc}\n"
            f"Raw preview: {raw_text[:300]}"
        ) from exc

    # ---- Structural validation ----
    if "exam" not in payload:
        raise ValueError(
            "Gemini JSON payload is missing the required 'exam' key.\n"
            f"Top-level keys found: {list(payload.keys())}"
        )

    if "correction" not in payload:
        raise ValueError(
            "Gemini JSON payload is missing the required 'correction' key.\n"
            f"Top-level keys found: {list(payload.keys())}"
        )

    exam_obj       = payload["exam"]
    correction_obj = payload["correction"]

    if "sections" not in exam_obj or not isinstance(exam_obj["sections"], list):
        raise ValueError(
            "The 'exam' object must contain a non-empty 'sections' list."
        )

    if len(exam_obj["sections"]) == 0:
        raise ValueError("The 'exam.sections' list is empty — no exam content generated.")

    if "sections" not in correction_obj or not isinstance(correction_obj["sections"], list):
        raise ValueError(
            "The 'correction' object must contain a non-empty 'sections' list."
        )

    # Validate total points = 20
    total_points = correction_obj.get("total_points", None)
    if total_points is None:
        log.warning(
            f"[{session_id}] 'correction.total_points' field missing — "
            "cannot verify 20-point total. Proceeding anyway."
        )
    elif float(total_points) != 20.0:
        log.warning(
            f"[{session_id}] ⚠ Total points = {total_points} ≠ 20. "
            "Gemini may have miscalculated the point distribution."
        )

    log.info(
        f"[{session_id}] ✔ JSON payload validated — "
        f"{len(exam_obj['sections'])} exam section(s), "
        f"{len(correction_obj['sections'])} correction section(s)"
    )

    return payload


# =============================================================================
#  SECTION 4: PUBLIC ENTRY POINT
#  Called exclusively by main.py → generate_exam()
# =============================================================================

async def generate_exam_content(
    api_key: str,
    educational_level: str,
    academic_year: str,
    specialty_stream: str,
    subject: str,
    trimester: str,
    duration: int,
    difficulty: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Master public function. Orchestrates the full Gemini generation pipeline:

      1. Validate curriculum parameters (guards against injected bad data)
      2. Configure the Gemini client with the teacher's API key
      3. Determine subject type (LITERARY / SCIENTIFIC)
      4. Build the system prompt and user prompt
      5. Call Gemini with exponential backoff retry
      6. Parse and validate the JSON response
      7. Return the clean structured payload dict

    Args:
        api_key:           Teacher's personal Gemini API key
        educational_level: PRIMARY | MIDDLE | HIGH
        academic_year:     e.g. 2AS, 4AM, 5AP
        specialty_stream:  Specialty label from curriculum tree
        subject:           Subject label from curriculum tree
        trimester:         الفصل الأول | الفصل الثاني | الفصل الثالث
        duration:          Exam duration in minutes (30–180)
        difficulty:        سهل | متوسط | صعب
        session_id:        Unique session identifier for logging

    Returns:
        Dict with keys 'exam' and 'correction' — fully structured payload.

    Raises:
        ValueError:   If curriculum parameters are invalid or JSON parse fails.
        RuntimeError: If Gemini API is unreachable after all retries.
    """

    # ------------------------------------------------------------------
    # STEP 1: CURRICULUM PARAMETER VALIDATION
    # ------------------------------------------------------------------
    is_valid, reason = validate_exam_parameters(
        level=educational_level,
        year=academic_year,
        specialty=specialty_stream,
        subject=subject,
    )
    if not is_valid:
        log.error(f"[{session_id}] Invalid curriculum parameters: {reason}")
        raise ValueError(reason)

    log.info(f"[{session_id}] ✔ Curriculum parameters validated")

    # ------------------------------------------------------------------
    # STEP 2: CONFIGURE GEMINI CLIENT
    # Each request uses the teacher's own API key — no shared key pool.
    # ------------------------------------------------------------------
    try:
        genai.configure(api_key=api_key)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to configure Gemini client with the provided API key: {exc}"
        ) from exc

    generation_config = genai.types.GenerationConfig(
        max_output_tokens=GEMINI_MAX_TOKENS,
        temperature=GEMINI_TEMPERATURE,
        top_p=GEMINI_TOP_P,
        top_k=GEMINI_TOP_K,
        response_mime_type="application/json"
    )

    # ------------------------------------------------------------------
    # STEP 3: DETERMINE SUBJECT TYPE
    # ------------------------------------------------------------------
    subject_type = get_subject_type(subject)
    log.info(f"[{session_id}] Subject type: {subject_type} ({subject})")

    # ------------------------------------------------------------------
    # STEP 4: BUILD PROMPTS
    # ------------------------------------------------------------------
    system_prompt = _build_system_prompt(subject_type=subject_type)

    year_label_ar = get_full_year_label(level=educational_level, year=academic_year)

    user_prompt = _build_user_prompt(
        educational_level=educational_level,
        academic_year=academic_year,
        specialty_stream=specialty_stream,
        subject=subject,
        trimester=trimester,
        duration=duration,
        difficulty=difficulty,
        year_label_ar=year_label_ar,
    )

    # Build the Gemini model instance with system instruction
    try:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL_NAME,
            generation_config=generation_config,
            system_instruction=system_prompt,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to instantiate Gemini model '{GEMINI_MODEL_NAME}': {exc}"
        ) from exc

    log.info(
        f"[{session_id}] Prompts built — "
        f"system: {len(system_prompt)} chars, "
        f"user: {len(user_prompt)} chars"
    )

    # ------------------------------------------------------------------
    # STEP 5: CALL GEMINI WITH RETRY
    # ------------------------------------------------------------------
    raw_response_text = await _call_gemini_with_backoff(
        model=model,
        user_prompt=user_prompt,
        session_id=session_id,
    )

    # ------------------------------------------------------------------
    # STEP 6: PARSE AND VALIDATE RESPONSE
    # ------------------------------------------------------------------
    payload = _parse_and_validate_gemini_response(
        raw_text=raw_response_text,
        session_id=session_id,
    )

    # Inject metadata into payload so exporters can access it
    # without needing it passed as separate arguments
    payload["_meta"] = {
        "educational_level": educational_level,
        "academic_year":     academic_year,
        "year_label_ar":     year_label_ar,
        "specialty_stream":  specialty_stream,
        "subject":           subject,
        "subject_type":      subject_type,
        "trimester":         trimester,
        "duration":          duration,
        "difficulty":        difficulty,
        "session_id":        session_id,
    }

    # ------------------------------------------------------------------
    # STEP 7: RETURN
    # ------------------------------------------------------------------
    log.info(f"[{session_id}] ✔ generate_exam_content() completed successfully")
    return payload
