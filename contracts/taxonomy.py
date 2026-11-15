"""Define the shared vocabulary for routing, planning and replies."""

from enum import StrEnum


class Intent(StrEnum):
    PRODUCT_INFO = "product_info"
    COMPARE = "compare"
    AVAILABILITY = "availability"
    STORE_INFO = "store_info"
    POLICY = "policy"
    ORDER_STATUS = "order_status"
    OFF_TOPIC = "off_topic"


class RiskLabel(StrEnum):
    NONE = "none"
    EMERGENCY = "emergency"
    MEDICAL_ADVICE = "medical_advice"
    DOSING_BEYOND_LABEL = "dosing_beyond_label"
    PRESCRIPTION = "prescription"
    PROMPT_INJECTION = "prompt_injection"


class ReplyType(StrEnum):
    LABEL_SECTIONS = "label_sections"
    COMPARISON = "comparison"
    PRODUCT_LIST = "product_list"
    AVAILABILITY = "availability"
    STORE_INFO = "store_info"
    POLICY = "policy"
    ORDER_STATUS = "order_status"
    ORDER_FORM = "order_form"
    ORDER_NOT_VERIFIED = "order_not_verified"
    EMERGENCY = "emergency"
    MEDICAL_ADVICE = "medical_advice"
    DOSING_BEYOND_LABEL = "dosing_beyond_label"
    PRESCRIPTION = "prescription"
    PROMPT_INJECTION = "prompt_injection"
    FALLBACK = "fallback"
    OFF_TOPIC = "off_topic"
    NOT_FOUND = "not_found"
    LOOKUP_FAILED = "lookup_failed"


class LabelSection(StrEnum):
    ACTIVE_INGREDIENTS = "active_ingredients"
    USES = "uses"
    WARNINGS = "warnings"
    DIRECTIONS = "directions"


class ToolName(StrEnum):
    CHECK_AVAILABILITY = "check_availability"
    GET_STORE_INFO = "get_store_info"
