from backend.app.llm.provider import (
    PROVIDER_UNAVAILABLE_MESSAGE,
    ChatProvider,
    ChatProviderError,
    ChatProviderResult,
)
from backend.app.llm.types import ChatProviderRequest


class FallbackChatProvider:
    def __init__(
        self,
        primary: ChatProvider,
        fallback: ChatProvider,
    ) -> None:
        self.name = primary.name
        self._primary = primary
        self._fallback = fallback

    async def generate_reply(
        self,
        request: ChatProviderRequest,
    ) -> ChatProviderResult:
        try:
            return await self._primary.generate_reply(request)
        except ChatProviderError:
            try:
                result = await self._fallback.generate_reply(request)
            except ChatProviderError:
                raise ChatProviderError(PROVIDER_UNAVAILABLE_MESSAGE) from None
            return result.model_copy(update={"fallback_used": True})
