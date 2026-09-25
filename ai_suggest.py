import json
import os
import re
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_SECONDS = 20
MAX_SUGGESTIONS = 3


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if key:
        return key

    env_file = Path(__file__).parent / ".env"

    if env_file.exists():
        for line in env_file.read_text(
            encoding="utf-8"
        ).splitlines():
            line = line.strip()

            if (
                not line
                or line.startswith("#")
                or "=" not in line
            ):
                continue

            name, value = line.split("=", 1)

            if name.strip() == "ANTHROPIC_API_KEY":
                return value.strip().strip('"').strip("'")

    return ""


def build_prompt(new_task, candidates):
    catalog = "\n".join(
        "%d: %s" % (candidate["id"], candidate["title"])
        for candidate in candidates
    )

    return (
        "You are helping plan a software project board.\n\n"
        "EXISTING TASKS (these are the only tasks that exist):\n"
        + catalog
        + "\n\n"
        "NEW TASK TITLE: "
        + new_task["title"]
        + "\n"
        "NEW TASK NOTES: "
        + (new_task.get("description") or "(none)")
        + "\n\n"
        "Which of the EXISTING TASKS must be finished before "
        "the NEW TASK can start?\n"
        "Rules you must follow exactly:\n"
        "- Choose only from the numeric ids listed above. "
        "Never invent a task or an id.\n"
        "- Choose at most %d. If none apply, return an empty list.\n"
        "- Give a reason of at most 12 words for each choice.\n"
        "- Reply with JSON only, in exactly this shape:\n"
        ' {"suggestions": [{"id": 3, "reason": "short reason"}]}\n'
        "- No markdown, no code fences, no text before or after the JSON."
        % MAX_SUGGESTIONS
    )


def extract_json(text):
    if not text:
        return None

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def call_llm(prompt):
    if requests is None:
        print(
            "[ai] the 'requests' package is not installed; "
            "using the fallback."
        )
        return None

    api_key = load_api_key()

    if not api_key:
        print(
            "[ai] no ANTHROPIC_API_KEY found; using the fallback."
        )
        return None

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": MODEL,
        "max_tokens": 400,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    try:
        response = requests.post(
            ANTHROPIC_URL,
            headers=headers,
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except Exception as error:
        print(
            "[ai] network problem: %s; using the fallback."
            % error
        )
        return None

    if response.status_code != 200:
        print(
            "[ai] API returned %d: %s"
            % (
                response.status_code,
                response.text[:300],
            )
        )
        return None

    try:
        blocks = response.json().get("content", [])

        for block in blocks:
            if block.get("type") == "text":
                return block.get("text")

    except (ValueError, KeyError, TypeError):
        return None

    return None


def keyword_suggestions(new_task, candidates, limit=MAX_SUGGESTIONS):
    text = (
        new_task.get("title", "")
        + " "
        + new_task.get("description", "")
    ).lower()

    scored = []

    for candidate in candidates:
        candidate_text = (
            candidate["title"]
            + " "
            + candidate.get("description", "")
        ).lower()

        words = set(
            re.findall(r"[a-z0-9]+", text)
        )

        candidate_words = set(
            re.findall(r"[a-z0-9]+", candidate_text)
        )

        overlap = words & candidate_words

        score = len(overlap)

        if score <= 0:
            continue

        reason = (
            "Shares planning keywords: "
            + ", ".join(sorted(overlap)[:3])
        )

        scored.append(
            (
                score,
                candidate["id"],
                reason,
            )
        )

    scored.sort(
        key=lambda row: (-row[0], row[1])
    )

    return [
        {
            "id": task_id,
            "reason": reason,
        }
        for _, task_id, reason in scored[:limit]
    ]