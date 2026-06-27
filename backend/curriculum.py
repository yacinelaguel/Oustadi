# =============================================================================
#  OSTADI — أستاذي
#  Algerian National Education Curriculum Data Dictionary
#  Architect: Yacine Laguel
#  File: backend/curriculum.py
#
#  This module is the single source of truth for the entire Algerian
#  Ministry of National Education curriculum tree.
#  It encodes every level, every year, every specialty branch, and every
#  subject with full Arabic labels exactly as they appear in official
#  Ministry of Education documentation.
#
#  The cascading dropdown system in main.py queries exclusively from
#  this dictionary. No hardcoded strings exist anywhere else in the backend.
# =============================================================================

from __future__ import annotations
from typing import Dict, List, Optional, Any


# =============================================================================
#  SECTION 1: RAW CURRICULUM TREE
#  Structure:
#    CURRICULUM_TREE[level_id][year_code][specialty_label] = [subject_list]
#
#  Special sentinel: if a level/year has no specialty distinction,
#  the specialty key is set to the constant SINGLE_TRACK_KEY below.
# =============================================================================

SINGLE_TRACK_KEY = "مسار عام"   # "General Track" — used for PRIMARY and MIDDLE


CURRICULUM_TREE: Dict[str, Any] = {

    # =========================================================================
    # PRIMARY LEVEL — الطور الابتدائي
    # Grades: 1AP through 5AP
    # Stream: General track only (no specialty branching)
    # =========================================================================
    "PRIMARY": {

        "1AP": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية",
                "الرياضيات",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية الفنية",
                "التربية البدنية والرياضية",
            ]
        },

        "2AP": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية",
                "الرياضيات",
                "اللغة الفرنسية",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية الفنية",
                "التربية البدنية والرياضية",
            ]
        },

        "3AP": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية",
                "الرياضيات",
                "اللغة الفرنسية",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية العلمية والتكنولوجية",
                "التربية الفنية",
                "التربية البدنية والرياضية",
            ]
        },

        "4AP": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية",
                "الرياضيات",
                "اللغة الفرنسية",
                "التربية الإسلامية",
                "التربية المدنية",
                "التاريخ والجغرافيا",
                "التربية العلمية والتكنولوجية",
                "التربية الفنية",
                "التربية البدنية والرياضية",
            ]
        },

        "5AP": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية",
                "الرياضيات",
                "اللغة الفرنسية",
                "التربية الإسلامية",
                "التربية المدنية",
                "التاريخ والجغرافيا",
                "التربية العلمية والتكنولوجية",
                "التربية الفنية",
                "التربية البدنية والرياضية",
            ]
        },
    },


    # =========================================================================
    # MIDDLE SCHOOL LEVEL — الطور المتوسط (CEM)
    # Grades: 1AM through 4AM
    # Stream: General track only (no specialty branching)
    # =========================================================================
    "MIDDLE": {

        "1AM": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "علوم الطبيعة والحياة",
                "العلوم الفيزيائية والتكنولوجيا",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية الفنية والموسيقية",
                "التربية البدنية والرياضية",
            ]
        },

        "2AM": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "علوم الطبيعة والحياة",
                "العلوم الفيزيائية والتكنولوجيا",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية الفنية والموسيقية",
                "التربية البدنية والرياضية",
            ]
        },

        "3AM": {
            SINGLE_TRACK_KEY: [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "علوم الطبيعة والحياة",
                "العلوم الفيزيائية والتكنولوجيا",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية الفنية والموسيقية",
                "التربية البدنية والرياضية",
            ]
        },

        "4AM": {
            # 4AM is the BEM preparatory year — same general track,
            # subject load identical, examination pressure increases.
            SINGLE_TRACK_KEY: [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "علوم الطبيعة والحياة",
                "العلوم الفيزيائية والتكنولوجيا",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية المدنية",
                "التربية الفنية والموسيقية",
                "التربية البدنية والرياضية",
            ]
        },
    },


    # =========================================================================
    # HIGH SCHOOL LEVEL — الطور الثانوي (Lycée)
    # Grades: 1AS, 2AS, 3AS
    #
    # STRICT BRANCHING LAW (per Ministry specification):
    #   1AS → Two common-core trunks only (جذع مشترك)
    #   2AS / 3AS → Six full specialties with distinct subject maps
    # =========================================================================
    "HIGH": {

        # ---------------------------------------------------------------------
        # 1AS — Common Core Year (جذع مشترك)
        # No final specialty yet — two trunks only
        # ---------------------------------------------------------------------
        "1AS": {

            "جذع مشترك علوم وتكنولوجيا": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "علوم الطبيعة والحياة",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "جذع مشترك آداب": [
                "اللغة العربية وآدابها",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "الفلسفة",
                "التربية الإسلامية",
                "الرياضيات",
                "التربية البدنية والرياضية",
            ],
        },

        # ---------------------------------------------------------------------
        # 2AS — Full Specialty Branching
        # ---------------------------------------------------------------------
        "2AS": {

            "علوم تجريبية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "علوم الطبيعة والحياة",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "رياضيات": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "علوم الطبيعة والحياة",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة مدنية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "الهندسة المدنية",
                "رسم هندسي ومعماري",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة كهربائية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "الهندسة الكهربائية",
                "الإلكترونيك",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة ميكانيكية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "الهندسة الميكانيكية",
                "تقنيات تصنيع",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة الطرائق": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "هندسة الطرائق والكيمياء الصناعية",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تسيير واقتصاد": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "الاقتصاد والمناجمنت",
                "محاسبة مالية",
                "قانون واقتصاد",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "آداب وفلسفة": [
                "اللغة العربية وآدابها",
                "الفلسفة",
                "التاريخ والجغرافيا",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التربية الإسلامية",
                "الرياضيات",
                "علم الاجتماع والنفس",
                "التربية البدنية والرياضية",
            ],

            "لغات أجنبية": [
                "اللغة العربية وآدابها",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "اللغة الإسبانية / الألمانية / الإيطالية",
                "التاريخ والجغرافيا",
                "الفلسفة",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],
        },

        # ---------------------------------------------------------------------
        # 3AS — BAC Preparatory Year
        # Same specialty branches as 2AS — subject load is identical
        # with increased depth and official BAC-oriented weighting.
        # ---------------------------------------------------------------------
        "3AS": {

            "علوم تجريبية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "علوم الطبيعة والحياة",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "رياضيات": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "علوم الطبيعة والحياة",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة مدنية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "الهندسة المدنية",
                "رسم هندسي ومعماري",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة كهربائية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "الهندسة الكهربائية",
                "الإلكترونيك",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة ميكانيكية": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "الهندسة الميكانيكية",
                "تقنيات تصنيع",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تقني رياضي — هندسة الطرائق": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "العلوم الفيزيائية والتكنولوجيا",
                "هندسة الطرائق والكيمياء الصناعية",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "تسيير واقتصاد": [
                "اللغة العربية وآدابها",
                "الرياضيات",
                "الاقتصاد والمناجمنت",
                "محاسبة مالية",
                "قانون واقتصاد",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التاريخ والجغرافيا",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],

            "آداب وفلسفة": [
                "اللغة العربية وآدابها",
                "الفلسفة",
                "التاريخ والجغرافيا",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "التربية الإسلامية",
                "الرياضيات",
                "علم الاجتماع والنفس",
                "التربية البدنية والرياضية",
            ],

            "لغات أجنبية": [
                "اللغة العربية وآدابها",
                "اللغة الفرنسية",
                "اللغة الإنجليزية",
                "اللغة الإسبانية / الألمانية / الإيطالية",
                "التاريخ والجغرافيا",
                "الفلسفة",
                "التربية الإسلامية",
                "التربية البدنية والرياضية",
            ],
        },
    },
}


# =============================================================================
#  SECTION 2: LEVEL METADATA
#  Human-readable labels and year-code ordered lists for each level.
#  Used to populate the first and second dropdowns.
# =============================================================================

LEVEL_METADATA: Dict[str, Dict[str, Any]] = {
    "PRIMARY": {
        "label_ar":  "الطور الابتدائي",
        "label_fr":  "Enseignement Primaire",
        "year_codes": ["1AP", "2AP", "3AP", "4AP", "5AP"],
        "year_labels": {
            "1AP": "السنة الأولى ابتدائي",
            "2AP": "السنة الثانية ابتدائي",
            "3AP": "السنة الثالثة ابتدائي",
            "4AP": "السنة الرابعة ابتدائي",
            "5AP": "السنة الخامسة ابتدائي",
        },
    },
    "MIDDLE": {
        "label_ar":  "الطور المتوسط",
        "label_fr":  "Enseignement Moyen (CEM)",
        "year_codes": ["1AM", "2AM", "3AM", "4AM"],
        "year_labels": {
            "1AM": "السنة الأولى متوسط",
            "2AM": "السنة الثانية متوسط",
            "3AM": "السنة الثالثة متوسط",
            "4AM": "السنة الرابعة متوسط (BEM)",
        },
    },
    "HIGH": {
        "label_ar":  "الطور الثانوي",
        "label_fr":  "Enseignement Secondaire (Lycée)",
        "year_codes": ["1AS", "2AS", "3AS"],
        "year_labels": {
            "1AS": "السنة الأولى ثانوي (جذع مشترك)",
            "2AS": "السنة الثانية ثانوي",
            "3AS": "السنة الثالثة ثانوي (BAC)",
        },
    },
}


# =============================================================================
#  SECTION 3: SUBJECT CLASSIFICATION MAP
#  Classifies every subject as either LITERARY or SCIENTIFIC.
#  Used by the Gemini prompt builder (gemini_service.py) to determine
#  which exam structure template to apply:
#    LITERARY  → نص + بناء فكري + بناء لغوي + وضعية إدماجية
#    SCIENTIFIC → تمرين 1 + تمرين 2 + مسألة إدماجية
# =============================================================================

SUBJECT_TYPE_MAP: Dict[str, str] = {
    # --- LITERARY SUBJECTS ---
    "اللغة العربية":                        "LITERARY",
    "اللغة العربية وآدابها":               "LITERARY",
    "اللغة الفرنسية":                       "LITERARY",
    "اللغة الإنجليزية":                     "LITERARY",
    "اللغة الإسبانية / الألمانية / الإيطالية": "LITERARY",
    "التربية الإسلامية":                    "LITERARY",
    "التربية المدنية":                       "LITERARY",
    "التاريخ والجغرافيا":                   "LITERARY",
    "الفلسفة":                               "LITERARY",
    "علم الاجتماع والنفس":                  "LITERARY",
    "قانون واقتصاد":                        "LITERARY",
    "الاقتصاد والمناجمنت":                 "LITERARY",

    # --- SCIENTIFIC SUBJECTS ---
    "الرياضيات":                             "SCIENTIFIC",
    "العلوم الفيزيائية والتكنولوجيا":      "SCIENTIFIC",
    "علوم الطبيعة والحياة":                 "SCIENTIFIC",
    "التربية العلمية والتكنولوجية":         "SCIENTIFIC",
    "الهندسة المدنية":                       "SCIENTIFIC",
    "رسم هندسي ومعماري":                    "SCIENTIFIC",
    "الهندسة الكهربائية":                   "SCIENTIFIC",
    "الإلكترونيك":                           "SCIENTIFIC",
    "الهندسة الميكانيكية":                  "SCIENTIFIC",
    "تقنيات تصنيع":                          "SCIENTIFIC",
    "هندسة الطرائق والكيمياء الصناعية":    "SCIENTIFIC",
    "محاسبة مالية":                          "SCIENTIFIC",
}


def get_subject_type(subject: str) -> str:
    """
    Returns 'LITERARY' or 'SCIENTIFIC' for a given subject label.
    Defaults to 'LITERARY' if the subject is not found in the map,
    since literary exam format is the safer structural fallback.
    """
    return SUBJECT_TYPE_MAP.get(subject, "LITERARY")


# =============================================================================
#  SECTION 4: PUBLIC QUERY FUNCTIONS
#  Called exclusively by main.py cascade endpoints.
#  All functions return None on invalid input (caller raises HTTP 404).
# =============================================================================

def get_years_for_level(level: str) -> Optional[List[Dict[str, str]]]:
    """
    Returns the ordered list of academic year objects for a given level.

    Each object has:
      - code:  the year identifier used in all subsequent API calls
      - label: the full Arabic label shown in the dropdown

    Returns None if the level is unrecognised.
    """
    meta = LEVEL_METADATA.get(level)
    if meta is None:
        return None

    return [
        {"code": code, "label": meta["year_labels"][code]}
        for code in meta["year_codes"]
    ]


def get_specialties_for_year(
    level: str,
    year: str,
) -> Optional[List[Dict[str, str]]]:
    """
    Returns the list of specialty/stream objects for a level + year pair.

    Each object has:
      - id:    the specialty label (used as dict key in curriculum tree)
      - label: identical to id (Arabic label is the canonical identifier)

    Returns None if the level or year is unrecognised.
    """
    level_data = CURRICULUM_TREE.get(level)
    if level_data is None:
        return None

    year_data = level_data.get(year)
    if year_data is None:
        return None

    return [
        {"id": specialty, "label": specialty}
        for specialty in year_data.keys()
    ]


def get_subjects_for_specialty(
    level: str,
    year: str,
    specialty: str,
) -> Optional[List[Dict[str, str]]]:
    """
    Returns the subject list for a level + year + specialty combination.

    Each object has:
      - id:    the subject label (used in Gemini prompt)
      - label: identical to id
      - type:  'LITERARY' or 'SCIENTIFIC' (used by exam template selector)

    Returns None if any key in the path is unrecognised.
    """
    try:
        subjects_raw: List[str] = CURRICULUM_TREE[level][year][specialty]
    except KeyError:
        return None

    return [
        {
            "id":    subject,
            "label": subject,
            "type":  get_subject_type(subject),
        }
        for subject in subjects_raw
    ]


def validate_exam_parameters(
    level: str,
    year: str,
    specialty: str,
    subject: str,
) -> tuple[bool, str]:
    """
    Validates that a complete set of exam parameters forms a valid path
    through the curriculum tree.

    Returns:
        (True, "")          — parameters are valid
        (False, reason_msg) — parameters are invalid, with Arabic + English reason

    Used by gemini_service.py before building the Gemini prompt, as a
    final guardrail against malformed requests that bypass Pydantic validation.
    """
    # Check level
    if level not in CURRICULUM_TREE:
        return False, (
            f"الطور التعليمي '{level}' غير معرّف في المنظومة. | "
            f"Educational level '{level}' is not defined."
        )

    # Check year
    if year not in CURRICULUM_TREE[level]:
        return False, (
            f"السنة الدراسية '{year}' غير موجودة ضمن الطور '{level}'. | "
            f"Academic year '{year}' is not valid for level '{level}'."
        )

    # Check specialty
    if specialty not in CURRICULUM_TREE[level][year]:
        return False, (
            f"الشعبة '{specialty}' غير مدرجة ضمن '{year}'. | "
            f"Specialty '{specialty}' is not valid for year '{year}'."
        )

    # Check subject
    valid_subjects = CURRICULUM_TREE[level][year][specialty]
    if subject not in valid_subjects:
        return False, (
            f"المادة '{subject}' لا تنتمي إلى شعبة '{specialty}' في '{year}'. | "
            f"Subject '{subject}' is not taught in specialty '{specialty}' / year '{year}'."
        )

    return True, ""


def get_full_year_label(level: str, year: str) -> str:
    """
    Returns the full Arabic year label for use in the PDF/DOCX header.
    Example: get_full_year_label("HIGH", "2AS") → "السنة الثانية ثانوي"
    Falls back to the raw year code if the label is not found.
    """
    try:
        return LEVEL_METADATA[level]["year_labels"][year]
    except KeyError:
        return year