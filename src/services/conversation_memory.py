MAX_MEMORY_MESSAGES = 6
MAX_MESSAGE_CHARS = 1200


def prepare_recent_history(
    messages,
    *,
    max_messages=MAX_MEMORY_MESSAGES,
    max_message_chars=MAX_MESSAGE_CHARS,
):
    """Return a small, text-only conversation window for follow-up resolution."""

    if not isinstance(messages, (list, tuple)):
        return []

    prepared = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue

        content = str(message.get("content") or "").strip()
        if not content:
            continue

        if len(content) > max_message_chars:
            content = content[:max_message_chars].rstrip() + "…"

        prepared.append(
            {
                "role": role,
                "content": content,
            }
        )

    return prepared[-max_messages:]
