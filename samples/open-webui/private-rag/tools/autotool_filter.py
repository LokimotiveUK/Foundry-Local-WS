"""
title: AutoTool Filter (Job Search)
description: Auto-selects the Job Search RAG tool whenever the chat mentions resumes, CVs, cover letters, or job applications.
author: foundry-local
version: 0.2.0
required_open_webui_version: 0.5.0
"""

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from open_webui.models.tools import Tools
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.misc import get_last_user_message


class Filter:
    class Valves(BaseModel):
        template: str = Field(
            default=(
                """Tools: {{TOOLS}}\n"
                "Decide whether the query requires the job_search_rag tool.\n"
                "Return ['job_search_rag'] if the user asks about resumes, CVs, cover letters, job applications, work history, skills, or ATS optimisation.\n"
                "If the request isn't about the user's job-search documents, return [].\n"
                "Only reply with a JSON list like ['job_search_rag'] or [].\n"
            """
            ),
            description="Prompt used to decide which tool IDs to force on the request.",
        )
        status: bool = Field(
            default=True,
            description="Show status messages in the chat event stream while the filter runs.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __event_emitter__: Callable[[Any], Awaitable[None]],
        __request__: Any,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
    ) -> dict:
        messages = body["messages"]
        user_message = get_last_user_message(messages)

        available_tool_ids = __model__.get("info", {}).get("meta", {}).get("toolIds", [])
        all_tools = [
            {"id": tool.id, "description": tool.meta.description}
            for tool in Tools.get_tools()
            if tool.id in available_tool_ids
        ]

        if not all_tools or not user_message:
            return body

        if self.valves.status:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Selecting Job Search tool…", "done": False},
                }
            )

        system_prompt = self.valves.template.replace("{{TOOLS}}", json.dumps(all_tools))
        history = "\n".join(
            [
                f"{message['role'].upper()}: \"\"\"{message['content']}\"\"\""
                for message in messages[::-1][:4]
            ]
        )
        payload = {
            "model": body["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"History:\n{history}\n\nQuery: {user_message}",
                },
            ],
            "stream": False,
        }

        try:
            user = Users.get_user_by_id(__user__["id"]) if __user__ else None
            response = await generate_chat_completion(
                request=__request__,
                form_data=payload,
                user=user,
            )
            content = response["choices"][0]["message"].get("content", "")
            if content:
                content = re.sub(r"'", '"', content)
                match = re.search(r"\[.*?\]", content)
                if match:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list) and parsed:
                        body["tool_ids"] = parsed
                        if self.valves.status:
                            await __event_emitter__(
                                {
                                    "type": "status",
                                    "data": {
                                        "description": f"AutoTool selected: {', '.join(parsed)}",
                                        "done": True,
                                    },
                                }
                            )
                        return body
        except Exception as e:  # pragma: no cover - diagnostic aid
            if self.valves.status:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"AutoTool error: {e}", "done": True},
                    }
                )
            return body

        if self.valves.status:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "AutoTool skipped (no match)", "done": True},
                }
            )
        return body
