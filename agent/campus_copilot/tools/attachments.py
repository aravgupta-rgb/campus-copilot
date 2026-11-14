"""Find the most recent file the student attached (image or PDF) in the chat."""

from __future__ import annotations

from google.adk.tools import ToolContext
from google.genai import types


def latest_attachment(tool_context: ToolContext, kinds: tuple[str, ...] = ("image/",)) -> types.Part | None:
    """Newest user-attached part whose MIME type starts with one of `kinds`."""
    contents = []
    if tool_context.user_content:
        contents.append(tool_context.user_content)
    try:
        events = tool_context.get_invocation_context().session.events
        contents += [e.content for e in reversed(events) if e.author == "user" and e.content]
    except Exception:  # if the session shape changes, the current message is enough
        pass
    for content in contents:
        for part in content.parts or []:
            blob = part.inline_data
            if blob and blob.mime_type and blob.mime_type.startswith(kinds):
                return part
    return None
