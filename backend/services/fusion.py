"""Weighted fusion of voice, intent, caller, and behavior signals."""

from __future__ import annotations

from collections.abc import Iterable

try:
    from ..schemas import BehaviorResult, CallerResult, FusedResult, IntentResult, ScoreBreakdown, VoiceResult
except ImportError:  # Supports imports when running from backend/.
    from schemas import BehaviorResult, CallerResult, FusedResult, IntentResult, ScoreBreakdown, VoiceResult

WEIGHT_VOICE = 0.20
WEIGHT_INTENT = 0.40
WEIGHT_CALLER = 0.20
WEIGHT_BEHAVIOR = 0.20
THRESHOLD_SAFE = 30.0
THRESHOLD_CRITICAL = 70.0
SCRIPT_BLEND_WEIGHT = 0.40
LLM_BLEND_WEIGHT = 0.60

_PATTERN_DISPLAY_STRINGS: dict[str, str] = {
    "authority_claim_en": "The caller claimed to represent an official authority.",
    "authority_claim_hi": "The caller used official-authority language.",
    "arrest_threat_en": "The caller used arrest or legal-threat language.",
    "arrest_threat_hi": "The caller used arrest or legal-threat language.",
    "secrecy_request_en": "The caller asked you to keep the conversation secret.",
    "secrecy_request_hi": "The caller asked you to keep the conversation secret.",
    "money_transfer_en": "The caller requested money, payment, or account details.",
    "money_transfer_hi": "The caller requested money, payment, or account details.",
    "aadhaar_crime_link_en": "The caller linked your identity or account to a supposed crime.",
    "aadhaar_crime_link_hi": "The caller linked your identity or account to a supposed crime.",
    "video_call_trap_en": "The caller pressured you to stay on a video call.",
    "video_call_trap_hi": "The caller pressured you to stay on a video call.",
    "remote_access_en": "The caller asked you to install software or share your screen.",
    "remote_access_hi": "The caller asked you to install software or share your screen.",
    "urgency_deadline_en": "The caller created urgency or imposed a deadline.",
    "urgency_deadline_hi": "The caller created urgency or imposed a deadline.",
    "identity_data_request_en": "The caller requested sensitive identity information.",
    "identity_data_request_hi": "The caller requested sensitive identity information.",
    "otp_request_en": "The caller requested a one-time password or verification code.",
    "otp_request_hi": "The caller requested a one-time password or verification code.",
    "sim_deactivation_en": "The caller threatened to deactivate your SIM or mobile number.",
    "sim_deactivation_hi": "The caller threatened to deactivate your SIM or mobile number.",
    "prize_lottery_en": "The caller used a prize or lottery payment story.",
    "prize_lottery_hi": "The caller used a prize or lottery payment story.",
    "impersonation_identity_en": "The caller used an unverified identity claim.",
    "impersonation_identity_hi": "The caller used an unverified identity claim.",
}


def reason_key_to_display_string(pattern_id: str) -> str:
    """Map an internal YAML pattern id to display-safe English copy."""

    if pattern_id in _PATTERN_DISPLAY_STRINGS:
        return _PATTERN_DISPLAY_STRINGS[pattern_id]
    return pattern_id.replace("_", " ").capitalize()


def _unique_reasons(reasons: Iterable[str], limit: int = 5) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for reason in reasons:
        clean = reason.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
        if len(result) >= limit:
            break
    return result


class FusionService:
    """Apply the documented risk weights and produce a final verdict."""

    def fuse(
        self,
        voice_result: VoiceResult,
        intent_result: IntentResult,
        caller_result: CallerResult,
        behavior_result: BehaviorResult,
    ) -> FusedResult:
        """Fuse four normalized signal sources into one user-facing result."""

        combined_intent = (
            SCRIPT_BLEND_WEIGHT * intent_result.script_score
            + LLM_BLEND_WEIGHT * intent_result.llm_intent_score
        )
        combined_intent = max(0.0, min(100.0, combined_intent))
        voice_score = voice_result.synthetic_probability * 100.0
        final_score = (
            WEIGHT_VOICE * voice_score
            + WEIGHT_INTENT * combined_intent
            + WEIGHT_CALLER * caller_result.caller_score
            + WEIGHT_BEHAVIOR * behavior_result.behavior_score
        )
        final_score = max(0.0, min(100.0, final_score))
        if final_score < THRESHOLD_SAFE:
            verdict = "SAFE"
        elif final_score > THRESHOLD_CRITICAL:
            verdict = "CRITICAL"
        else:
            verdict = "SUSPICIOUS"

        matched_patterns = list(dict.fromkeys(intent_result.detected_patterns))
        reasons: list[str] = [reason_key_to_display_string(pattern) for pattern in matched_patterns]
        if voice_score >= 55.0:
            reasons.append("The audio signal has characteristics associated with synthetic speech.")
        if caller_result.is_known_scammer or caller_result.report_count or caller_result.community_report_count:
            reasons.append(
                "This caller has community reports or prior risk history."
            )
        if intent_result.reasoning and intent_result.reasoning not in {
            "Parse error",
            "Groq unavailable; offline scanner signal used.",
        }:
            reasons.append(intent_result.reasoning)
        if behavior_result.behavior_score >= 55.0:
            reasons.append("The call's rolling behavior is escalating toward a high-risk pattern.")
        if not reasons:
            reasons.append("No strong scam indicators were detected in the latest call segment.")

        return FusedResult(
            final_score=round(final_score, 2),
            verdict=verdict,
            breakdown=ScoreBreakdown(
                voice=round(voice_score, 2),
                intent=round(combined_intent, 2),
                caller=round(caller_result.caller_score, 2),
                behavior=round(behavior_result.behavior_score, 2),
            ),
            reasons=_unique_reasons(reasons),
            matched_patterns=matched_patterns,
        )
