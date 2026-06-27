# =============================================================================
#  OSTADI — أستاذي
#  AI Service Engine (OpenRouter — Llama 3.3 70B)
#  Architect: Yacine Laguel
#  File: backend/gemini_service.py
#
#  Responsibilities:
#    1. Build the full Ministry-grade Arabic system prompt dynamically
#       from the exam parameters passed by main.py
#    2. Call OpenRouter API (Llama 3.3 70B) with full error handling
#    3. Implement exponential backoff retry on HTTP 429 (quota exceeded)
#    4. Parse and validate the JSON payload returned by the model
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
import httpx
from typing import Any, Dict

from curriculum import get_subject_type, get_full_year_label, validate_exam_parameters

# ---------------------------------------------------------------------------
# MODULE LOGGER
# ---------------------------------------------------------------------------
log = logging.getLogger("ostadi.gemini")

# ---------------------------------------------------------------------------
# RETRY POLICY CONSTANTS
# ---------------------------------------------------------------------------
MAX_RETRY_ATTEMPTS   = 2
BASE_BACKOFF_SECONDS = 15.0
BACKOFF_MULTIPLIER   = 2.0
MAX_BACKOFF_SECONDS  = 60.0
JITTER_RANGE         = 3.0

# ---------------------------------------------------------------------------
# OPENROUTER CONFIGURATION
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL  = "https://openrouter.ai/api/v1/chat/completions"
# Best free model for Arabic structured output
OPENROUTER_MODEL     = "meta-llama/llama-3.3-70b-instruct:free"
MAX_TOKENS           = 4096
TEMPERATURE          = 0.4
TOP_P                = 0.9


# =============================================================================
#  SECTION 1: SYSTEM PROMPT BUILDER
# =============================================================================

def _build_system_prompt(subject_type: str) -> str:
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
1. الالتزام الحرفي بالمخطط السنوي: يُحظر بشكل قاطع صياغة أي سؤال أو استخدام أي مصطلح لا ينتمي إلى الدروس المقررة رسمياً من الوزارة لهذا الفصل بعينه.
2. لغة الإخراج: اللغة العربية الفصحى السليمة في جميع أجزاء الموضوع والتصحيح دون استثناء، باستثناء المواد التي لغتها الفرنسية أو الإنجليزية فتكون بلغتها الأصلية.
3. دقة التنقيط: يجب أن يكون مجموع علامات الاختبار 20 نقطة بالضبط.

{structure_instructions}

التصحيح النموذجي وسلّم التنقيط:
يجب إنتاج ملحق منفصل تحت عنوان "التصحيح النموذجي وسلّم التنقيط الرسمي" يحتوي على إجابة نموذجية دقيقة لكل جزئية مع العلامة المخصصة.

CRITICAL INSTRUCTION: You MUST respond with ONLY a valid JSON object. No text before, no text after, no markdown, no ```json``` fences. Pure JSON only.

The required JSON structure:
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

IMPORTANT: Respond with ONLY the JSON object. No explanations, no markdown, no extra text."""


# =============================================================================
#  SECTION 2: OPENROUTER API CALL WITH RETRY
# =============================================================================

async def _call_openrouter_with_backoff(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    session_id: str,
) -> str:
    import random

    attempt = 0
    last_exception = None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://ostadi.onrender.com",
        "X-Title": "Ostadi - أستاذي",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens":   MAX_TOKENS,
        "temperature":  TEMPERATURE,
        "top_p":        TOP_P,
    }

    while attempt < MAX_RETRY_ATTEMPTS:
        attempt += 1
        log.info(f"[{session_id}] OpenRouter API call — attempt {attempt}/{MAX_RETRY_ATTEMPTS}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                )

            if response.status_code == 429:
                last_exception = Exception(f"Rate limited (429)")
                jitter = random.uniform(-JITTER_RANGE, JITTER_RANGE)
                wait = min(BASE_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1)), MAX_BACKOFF_SECONDS) + jitter
                wait = max(10.0, wait)
                log.warning(f"[{session_id}] ⚠ Rate limited — waiting {wait:.1f}s...")
                if attempt >= MAX_RETRY_ATTEMPTS:
                    raise RuntimeError(
                        "عذراً، تم تجاوز حصة الاستخدام. يرجى المحاولة بعد دقيقة."
                    )
                await asyncio.sleep(wait)
                continue

            if response.status_code == 402:
                raise RuntimeError(
                    "رصيد OpenRouter منتهٍ. يرجى التحقق من حسابك على openrouter.ai"
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"OpenRouter API error {response.status_code}: {response.text[:200]}"
                )

            data = response.json()

            # Extract text from response
            content = data["choices"][0]["message"]["content"]

            if not content or not content.strip():
                raise ValueError("OpenRouter returned an empty response.")

            log.info(f"[{session_id}] ✔ OpenRouter responded — {len(content)} characters")
            return content

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exception = exc
            jitter = random.uniform(0, JITTER_RANGE)
            wait = min(BASE_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1)), MAX_BACKOFF_SECONDS) + jitter
            log.warning(f"[{session_id}] ⚠ Network error — waiting {wait:.1f}s... ({exc})")
            if attempt >= MAX_RETRY_ATTEMPTS:
                raise RuntimeError("خطأ في الاتصال بالخدمة. يرجى المحاولة مجدداً.") from exc
            await asyncio.sleep(wait)

        except RuntimeError:
            raise

        except Exception as exc:
            log.error(f"[{session_id}] ✖ Unexpected error: {exc}", exc_info=True)
            raise RuntimeError(f"خطأ غير متوقع: {exc}") from exc

    raise RuntimeError(
        f"فشل الاتصال بالخدمة بعد {MAX_RETRY_ATTEMPTS} محاولات. آخر خطأ: {last_exception}"
    )


# =============================================================================
#  SECTION 3: JSON RESPONSE PARSER & VALIDATOR
# =============================================================================

def _parse_and_validate_response(
    raw_text: str,
    session_id: str,
) -> Dict[str, Any]:
    cleaned = raw_text.strip()

    # Strip markdown fences if model added them despite instructions
    fence_pattern = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
    match = fence_pattern.match(cleaned)
    if match:
        cleaned = match.group(1).strip()
        log.debug(f"[{session_id}] Stripped markdown fences from response")

    # Sometimes models add text before the JSON — find the first {
    if not cleaned.startswith("{"):
        brace_idx = cleaned.find("{")
        if brace_idx != -1:
            cleaned = cleaned[brace_idx:]
            log.debug(f"[{session_id}] Stripped preamble text before JSON")

    try:
        payload: Dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.error(
            f"[{session_id}] JSON decode failed.\n"
            f"Raw text preview (first 500 chars):\n{raw_text[:500]}"
        )
        raise ValueError(
            f"الاستجابة ليست JSON صالحاً: {exc}\n"
            f"معاينة: {raw_text[:300]}"
        ) from exc

    if "exam" not in payload:
        raise ValueError(f"مفتاح 'exam' مفقود. المفاتيح الموجودة: {list(payload.keys())}")

    if "correction" not in payload:
        raise ValueError(f"مفتاح 'correction' مفقود. المفاتيح الموجودة: {list(payload.keys())}")

    exam_obj       = payload["exam"]
    correction_obj = payload["correction"]

    if "sections" not in exam_obj or not isinstance(exam_obj["sections"], list):
        raise ValueError("يجب أن يحتوي 'exam' على قائمة 'sections'.")

    if len(exam_obj["sections"]) == 0:
        raise ValueError("قائمة 'exam.sections' فارغة.")

    if "sections" not in correction_obj or not isinstance(correction_obj["sections"], list):
        raise ValueError("يجب أن يحتوي 'correction' على قائمة 'sections'.")

    total_points = correction_obj.get("total_points")
    if total_points is not None and float(total_points) != 20.0:
        log.warning(f"[{session_id}] ⚠ Total points = {total_points} ≠ 20.")

    log.info(
        f"[{session_id}] ✔ JSON validated — "
        f"{len(exam_obj['sections'])} exam section(s)"
    )
    return payload


# =============================================================================
#  SECTION 4: PUBLIC ENTRY POINT
#  Same signature as before — main.py needs zero changes
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
    Public entry point — identical signature to the original Gemini version.
    Now uses OpenRouter (Llama 3.3 70B) instead of Gemini.
    main.py requires zero changes.
    """

    # STEP 1: Validate curriculum parameters
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

    # STEP 2: Determine subject type
    subject_type = get_subject_type(subject)
    log.info(f"[{session_id}] Subject type: {subject_type} ({subject})")

    # STEP 3: Build prompts
    system_prompt = _build_system_prompt(subject_type=subject_type)
    year_label_ar = get_full_year_label(level=educational_level, year=academic_year)
    user_prompt   = _build_user_prompt(
        educational_level=educational_level,
        academic_year=academic_year,
        specialty_stream=specialty_stream,
        subject=subject,
        trimester=trimester,
        duration=duration,
        difficulty=difficulty,
        year_label_ar=year_label_ar,
    )

    log.info(
        f"[{session_id}] Prompts built — "
        f"system: {len(system_prompt)} chars, user: {len(user_prompt)} chars"
    )

    # STEP 4: Call OpenRouter with retry
    raw_response_text = await _call_openrouter_with_backoff(
        api_key=api_key,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        session_id=session_id,
    )

    # STEP 5: Parse and validate response
    payload = _parse_and_validate_response(
        raw_text=raw_response_text,
        session_id=session_id,
    )

    # STEP 6: Inject metadata
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

    log.info(f"[{session_id}] ✔ generate_exam_content() completed successfully")
    return payload
