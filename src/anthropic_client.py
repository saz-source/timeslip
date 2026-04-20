"""
Anthropic API client — transforms raw work notes into structured Autotask drafts.
Output is always treated as a draft; the user must approve before any submission.
"""
import json
import re
from dataclasses import dataclass
from typing import Optional

import anthropic

from src.config import Config


SYSTEM_PROMPT = """You are an expert MSP (Managed Service Provider) technical writer.
Your job is to transform raw technician work notes into professional Autotask entries.

Rules:
- Be concise and professional. No fluff.
- Never write "performed the following tasks" or similar padding phrases.
- Use clean, billable MSP language that IT managers expect.
- Ticket titles: short, descriptive, action-oriented (e.g. "Workstation Replacement and Printer Relocation").
- Summaries: structured prose or a tight bullet list — readable, scannable, complete.
- Infer onsite vs offsite from context clues ("on-site", "drove to", "at the office" = onsite; "remote", "RDP", "TeamViewer", "Zoom", "called" = offsite). If unclear, set work_mode to "unknown".
- Return ONLY valid JSON — no markdown fences, no commentary, no preamble.

Required JSON schema:
{
  "title": "Short professional ticket title",
  "summary": "Professional internal notes / summary body",
  "work_mode": "onsite" | "offsite" | "unknown",
  "confidence": 0.0 to 1.0
}"""


@dataclass
class AIResult:
    title: str
    summary: str
    work_mode: str          # "onsite" | "offsite" | "unknown"
    confidence: float
    raw_response: str       # preserved for debugging


class AnthropicClient:
    def __init__(self, config: Config) -> None:
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def transform_notes(
        self,
        raw_notes: str,
        client_name: str,
        duration_hours: float,
    ) -> AIResult:
        """
        Send raw notes to Claude and return a structured AI draft.
        Raises ValueError if the response cannot be parsed.
        """
        user_message = (
            f"Client: {client_name}\n"
            f"Duration: {duration_hours:.2f} hours\n\n"
            f"Raw notes:\n{raw_notes.strip()}"
        )

        message = self._client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = message.content[0].text.strip()
        return self._parse_response(raw_text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(self, raw_text: str) -> AIResult:
        """Parse and validate the model's JSON response with fallback handling."""
        # Strip accidental markdown fences
        cleaned = re.sub(r"```(?:json)?", "", raw_text).strip().rstrip("`").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"AI response was not valid JSON.\n"
                f"Raw response:\n{raw_text}\n"
                f"Parse error: {exc}"
            ) from exc

        title = self._require_str(data, "title", raw_text)
        summary = self._require_str(data, "summary", raw_text)

        work_mode = str(data.get("work_mode", "unknown")).lower()
        if work_mode not in {"onsite", "offsite", "unknown"}:
            work_mode = "unknown"

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return AIResult(
            title=title.strip(),
            summary=summary.strip(),
            work_mode=work_mode,
            confidence=confidence,
            raw_response=raw_text,
        )

    @staticmethod
    def _require_str(data: dict, key: str, raw: str) -> str:
        val = data.get(key)
        if not val or not isinstance(val, str):
            raise ValueError(
                f"AI response missing required field '{key}'.\nRaw: {raw}"
            )
        return val
