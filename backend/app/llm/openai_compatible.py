from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from backend.app.llm.provider import (
    PROVIDER_UNAVAILABLE_MESSAGE,
    ChatProviderError,
    ChatProviderResult,
)
from backend.app.llm.types import ChatProviderRequest
from backend.app.schemas.chat import ChatEmotion


class _ProviderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1, max_length=500)
    emotion: ChatEmotion

    @field_validator("reply", mode="before")
    @classmethod
    def strip_reply(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class OpenAICompatibleChatProvider:
    """Provider-neutral adapter for OpenAI-compatible chat completion APIs."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        auth_mode: Literal["bearer", "none"],
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name = name.strip()
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._auth_mode = auth_mode
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def generate_reply(
        self,
        request: ChatProviderRequest,
    ) -> ChatProviderResult:
        headers = {"Content-Type": "application/json"}
        if self._auth_mode == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = {
            "model": self._model,
            "messages": self._build_messages(request),
            "temperature": 0.2,
        }

        try:
            if self._client is None:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self._endpoint,
                        headers=headers,
                        json=body,
                        timeout=self._timeout_seconds,
                    )
            else:
                response = await self._client.post(
                    self._endpoint,
                    headers=headers,
                    json=body,
                    timeout=self._timeout_seconds,
                )

            response.raise_for_status()
            response_body = response.json()
            content = response_body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Chat completion content must be text")
            payload = _ProviderPayload.model_validate_json(content)
            return ChatProviderResult(
                reply=payload.reply,
                emotion=payload.emotion,
                provider=self.name,
            )
        except (
            httpx.HTTPError,
            ValidationError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ):
            raise ChatProviderError(PROVIDER_UNAVAILABLE_MESSAGE) from None

    @staticmethod
    def _build_messages(request: ChatProviderRequest) -> list[dict[str, str]]:
        recent_actions = "\n".join(
            (
                f"- tick={action.tick}, time={action.world_time}, "
                f"action={action.action_type}, target={action.target_name or '-'}, "
                f"reason={action.reason_code}"
            )
            for action in request.recent_actions
        ) or "- none"
        personality = ", ".join(request.personality)
        system_content = "\n\n".join(
            (
                request.chat_system_prompt,
                f"[World lore]\n{request.world_lore}",
                f"[Character]\n{request.character_prompt}",
                (
                    "[Authoritative current state]\n"
                    f"World: {request.world_name} ({request.world_id})\n"
                    f"Day/time/tick: {request.world_day} / {request.world_time} / "
                    f"{request.world_tick}\n"
                    f"Time phase: {request.time_phase}\n"
                    f"NPC: {request.npc_name} ({request.npc_id}), role={request.role}\n"
                    f"Personality: {personality}\n"
                    f"Location: {request.location_name} ({request.location_id})\n"
                    f"Current action: {request.current_action}\n"
                    f"Energy/mood/social: {request.energy}/{request.mood}/"
                    f"{request.social}\n"
                    f"Recent actions:\n{recent_actions}"
                ),
                (
                    "Return exactly one JSON object with only these fields: "
                    '"reply" and "emotion". Do not return Markdown.'
                ),
            )
        )
        messages = [{"role": "system", "content": system_content}]
        messages.extend(
            {"role": history.role, "content": history.content}
            for history in request.conversation_history
        )
        messages.append({"role": "user", "content": request.player_message})
        return messages
