"""User-defined prompt templates (issue #90).
"""

from __future__ import annotations



from src.db import core
from src.db.core import (
    log,
    _execute_rowcount,
    _fetch_dicts,
    _fetch_one,
    generate_id,
)

# ---------------------------------------------------------------------------
# User-defined templates (issue #90)
# ---------------------------------------------------------------------------


async def list_user_templates(chat_id: int) -> list[dict]:
    """Return user-defined templates for this chat, ordered by name."""
    return await _fetch_dicts(
        "SELECT id, name, description, extra_instructions, trigger_patterns, "
        "brave_search, content_type_scope, created_at, updated_at "
        "FROM templates WHERE chat_id = ? AND is_builtin = 0 ORDER BY name",
        (chat_id,),
    )


async def get_user_template_by_name(chat_id: int, name: str) -> dict | None:
    """Return a user-defined template owned by this chat, or None."""
    row = await _fetch_one(
        "SELECT id, name, description, extra_instructions, trigger_patterns, "
        "brave_search, content_type_scope, created_at, updated_at "
        "FROM templates WHERE chat_id = ? AND name = ? AND is_builtin = 0",
        (chat_id, name),
    )
    return dict(row) if row else None


async def create_user_template(
    *,
    chat_id: int,
    name: str,
    description: str = "",
    extra_instructions: str = "",
) -> dict:
    """Insert a user-defined template scoped to chat_id and return the new row."""
    tmpl_id = generate_id()
    async with core.connection() as conn:
        await conn.execute(
            """INSERT INTO templates
               (id, chat_id, name, description, extra_instructions, is_builtin)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (tmpl_id, chat_id, name, description, extra_instructions),
        )
        await conn.commit()
    log.info("template_created", id=tmpl_id, chat_id=chat_id, name=name)
    return {
        "id": tmpl_id,
        "name": name,
        "description": description,
        "extra_instructions": extra_instructions,
        "trigger_patterns": "",
        "brave_search": 0,
        "content_type_scope": "",
        "is_builtin": False,
    }


async def update_user_template(
    *,
    chat_id: int,
    name: str,
    description: str = "",
    extra_instructions: str = "",
) -> bool:
    """Update a user template owned by this chat. Returns True if updated."""
    return (
        await _execute_rowcount(
            """UPDATE templates
           SET description = ?, extra_instructions = ?, updated_at = CURRENT_TIMESTAMP
           WHERE chat_id = ? AND name = ? AND is_builtin = 0""",
            (description, extra_instructions, chat_id, name),
        )
        > 0
    )


async def delete_user_template(chat_id: int, name: str) -> bool:
    """Delete a user template owned by this chat. Returns True if deleted."""
    return (
        await _execute_rowcount(
            "DELETE FROM templates WHERE chat_id = ? AND name = ? AND is_builtin = 0",
            (chat_id, name),
        )
        > 0
    )
