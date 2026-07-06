from __future__ import annotations

import re


def _normalize_login_phone(raw: str) -> str | None:
    raw = (raw or "").strip()
    digits = re.sub(r"\D+", "", raw)
    if raw.startswith("00") and len(digits) > 2:
        digits = digits[2:]
    if not 8 <= len(digits) <= 15:
        return None
    return f"+{digits}"


def _normalize_login_code(raw: str) -> str | None:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    return digits or None


def parse_bulk_phone_code_input(text: str) -> list[tuple[str, str]] | None:
    blocks = [
        [line.strip() for line in block.splitlines() if line.strip()]
        for block in re.split(r"\n\s*\n", text or "")
        if block.strip()
    ]

    if not blocks:
        return None

    if len(blocks) >= 2:
        phone_lines = blocks[0]
        code_lines = blocks[1]
    else:
        lines = blocks[0]
        if len(lines) < 2 or len(lines) % 2 != 0:
            return None
        split_at = len(lines) // 2
        phone_lines = lines[:split_at]
        code_lines = lines[split_at:]

    phones: list[str] = []
    for line in phone_lines:
        phone = _normalize_login_phone(line)
        if not phone:
            return None
        phones.append(phone)

    codes: list[str] = []
    for line in code_lines:
        code = _normalize_login_code(line)
        if not code:
            return None
        codes.append(code)

    if len(phones) != len(codes):
        return None

    return list(zip(phones, codes))
