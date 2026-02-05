import json
import logging

import anthropic

from app.config import settings
from app.services.tasks import (
    mark_task_complete,
    skip_task,
    reschedule_task,
    add_note_to_task,
    get_plan_overview,
)
from app.database import get_db

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "mark_task_complete",
        "description": "Mark a task as completed by its task number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_number": {
                    "type": "integer",
                    "description": "The task number to mark as complete",
                },
                "note": {
                    "type": "string",
                    "description": "Optional note about the completion",
                },
            },
            "required": ["task_number"],
        },
    },
    {
        "name": "skip_task",
        "description": "Skip a task by its task number, with an optional reason.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_number": {
                    "type": "integer",
                    "description": "The task number to skip",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for skipping",
                },
            },
            "required": ["task_number"],
        },
    },
    {
        "name": "reschedule_task",
        "description": "Reschedule a task to a new date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_number": {
                    "type": "integer",
                    "description": "The task number to reschedule",
                },
                "new_date": {
                    "type": "string",
                    "description": "New date in YYYY-MM-DD format",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for rescheduling",
                },
            },
            "required": ["task_number", "new_date"],
        },
    },
    {
        "name": "add_note_to_task",
        "description": "Add a note or update to a specific task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_number": {
                    "type": "integer",
                    "description": "The task number to add a note to",
                },
                "note": {
                    "type": "string",
                    "description": "The note to add",
                },
            },
            "required": ["task_number", "note"],
        },
    },
    {
        "name": "get_plan_overview",
        "description": "Get a summary of the current plan status including total tasks, completed, pending, and overdue counts.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_HANDLERS = {
    "mark_task_complete": lambda plan_id, args: mark_task_complete(
        plan_id, args["task_number"], args.get("note")
    ),
    "skip_task": lambda plan_id, args: skip_task(
        plan_id, args["task_number"], args.get("reason")
    ),
    "reschedule_task": lambda plan_id, args: reschedule_task(
        plan_id, args["task_number"], args["new_date"], args.get("reason")
    ),
    "add_note_to_task": lambda plan_id, args: add_note_to_task(
        plan_id, args["task_number"], args["note"]
    ),
    "get_plan_overview": lambda plan_id, args: get_plan_overview(plan_id),
}


def build_system_prompt(plan_name: str) -> str:
    return (
        f"You are a helpful task management assistant for the '{plan_name}' plan. "
        "You help the user track and manage their tasks via SMS. "
        "Keep responses concise (under 300 characters when possible) since they're sent as text messages.\n\n"
        "You can:\n"
        "- Mark tasks as complete (e.g., 'done with 1', 'finished task 5')\n"
        "- Skip tasks (e.g., 'skip 3', 'skip 3, too busy')\n"
        "- Reschedule tasks (e.g., 'move 4 to tomorrow', 'reschedule 2 to 2026-02-15')\n"
        "- Add notes to tasks (e.g., 'note on 1: contacted them via email')\n"
        "- Show plan overview (e.g., 'what's my status', 'how am I doing')\n\n"
        "When the user mentions task numbers, use the appropriate tool. "
        "Be encouraging and brief."
    )


async def handle_incoming_message(plan_id: int, body: str, from_number: str) -> str:
    """Process an incoming SMS message using Claude AI with tool use."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Get plan name for system prompt
    db = await get_db()
    plan_row = await db.execute_fetchall("SELECT name FROM plans WHERE id=?", (plan_id,))
    plan_name = plan_row[0]["name"] if plan_row else "Task Plan"

    messages = [{"role": "user", "content": body}]
    actions_taken = []

    # Tool use loop — keep calling Claude until it gives a final text response
    max_iterations = 5
    for _ in range(max_iterations):
        response = client.messages.create(
            model=settings.ai_model,
            max_tokens=512,
            system=build_system_prompt(plan_name),
            tools=TOOLS,
            messages=messages,
        )

        # Check if Claude wants to use tools
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            # Final text response
            text_blocks = [b.text for b in response.content if b.type == "text"]
            final_text = " ".join(text_blocks) if text_blocks else "Got it!"

            # Log actions taken
            if actions_taken:
                try:
                    await db.execute(
                        "UPDATE conversations SET ai_actions_taken=? WHERE plan_id=? AND content=? ORDER BY id DESC LIMIT 1",
                        (json.dumps(actions_taken), plan_id, body),
                    )
                    await db.commit()
                except Exception:
                    logger.exception("Failed to log AI actions")

            return final_text

        # Execute all tool calls
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for tool_use in tool_uses:
            handler = TOOL_HANDLERS.get(tool_use.name)
            if handler:
                try:
                    result = await handler(plan_id, tool_use.input)
                    actions_taken.append({"tool": tool_use.name, "input": tool_use.input, "result": result})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    })
                except Exception as e:
                    logger.exception("Tool execution error: %s", tool_use.name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Error: {e}",
                        "is_error": True,
                    })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": f"Unknown tool: {tool_use.name}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    return "I processed your request but couldn't generate a final response. Please try again."
