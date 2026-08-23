from backend.app.llm.provider import ChatProviderResult
from backend.app.llm.types import ChatProviderRequest
from backend.app.schemas.chat import ChatEmotion


class MockChatProvider:
    name = "mock"

    async def generate_reply(
        self,
        request: ChatProviderRequest,
    ) -> ChatProviderResult:
        message = request.player_message.casefold()

        if request.npc_id == "ryan":
            if self._contains(message, ("slime", "史莱姆")):
                return self._result(
                    "害怕？当然不是……我只是觉得史莱姆比看起来更麻烦。"
                    "保持警惕总没错。",
                    "guarded",
                )
            return self._result(
                "别担心，只要愿意向前走，我们总能找到办法。我会尽力帮你。",
                "cheerful",
            )

        if request.npc_id == "shir":
            if self._contains(
                message,
                ("sweet", "sweets", "cake", "candy", "糖", "甜", "蛋糕"),
            ):
                return self._result(
                    "……星辰酒馆的甜点还不错。只是偶尔尝尝。",
                    "reserved",
                )
            return self._result("……我听见了。说重点吧。", "reserved")

        if request.npc_id == "grey":
            if self._contains(
                message,
                ("ash war", "war", "ruin", "战争", "灰烬", "遗迹"),
            ):
                return self._result(
                    "有些旧事需要谨慎对待。现在知道得太多，未必安全。",
                    "concerned",
                )
            return self._result(
                "慢慢说。我会听着，也会留意周围是否安全。",
                "thoughtful",
            )

        return self._result("我听见了。我们可以慢慢聊。", "neutral")

    def _result(
        self,
        reply: str,
        emotion: ChatEmotion,
    ) -> ChatProviderResult:
        return ChatProviderResult(
            reply=reply,
            emotion=emotion,
            provider=self.name,
            fallback_used=False,
        )

    @staticmethod
    def _contains(message: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in message for keyword in keywords)
