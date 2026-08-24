from backend.app.llm.provider import ChatProviderResult
from backend.app.llm.types import ChatProviderRequest
from backend.app.schemas.chat import ChatEmotion


class MockChatProvider:
    name = "mock"

    _INTENT_KEYWORDS = (
        ("identity", ("你是谁", "叫什么", "身份", "who are you")),
        ("world", ("这里是哪里", "什么地方", "这个小镇", "where am i")),
        ("location", ("你现在在哪里", "你在哪", "当前位置", "where are you")),
        ("action", ("你在做什么", "正在做什么", "忙什么", "what are you doing")),
        ("mood", ("心情", "感觉怎么样", "过得怎么样", "how are you")),
        ("help", ("需要帮助", "帮帮我", "帮忙", "帮我", "help")),
        ("history", ("灰烬战争", "历史", "过去", "ash war", "history")),
        ("greeting", ("你好", "早上好", "晚上好", "hello", "hi")),
    )
    _QUEST_KEYWORDS = ("任务", "委托", "孩子", "线索", "quest")
    _ACTION_NAMES = {
        "rest": "休息",
        "work": "工作",
        "socialize": "交谈",
        "sleep": "睡觉",
        "travel": "移动",
    }

    async def generate_reply(
        self,
        request: ChatProviderRequest,
    ) -> ChatProviderResult:
        message = request.player_message.casefold()

        if request.npc_id not in {"ryan", "shir", "grey"}:
            return self._result("我听见了。我们可以慢慢聊。", "neutral")

        if (
            request.player_quest_context is not None
            and self._contains(message, self._QUEST_KEYWORDS)
        ):
            return self._quest_result(request)

        if request.npc_id == "ryan":
            if self._contains(message, ("slime", "史莱姆")):
                return self._result(
                    "害怕？当然不是……我只是觉得史莱姆比看起来更麻烦。"
                    "保持警惕总没错。",
                    "guarded",
                )

        if request.npc_id == "shir":
            if self._contains(
                message,
                ("sweet", "sweets", "cake", "candy", "糖", "甜", "蛋糕"),
            ):
                return self._result(
                    "……星辉酒馆的甜点还不错。只是偶尔尝尝。",
                    "reserved",
                )

        if request.npc_id == "grey":
            if self._contains(
                message,
                ("ash war", "war", "ruin", "战争", "灰烬", "遗迹"),
            ):
                return self._result(
                    "灰烬战争的记录并不完整，有些旧事需要谨慎核实。"
                    "我只会告诉你能确认的部分。",
                    "concerned",
                )

        intent = self._match_intent(message)
        return self._intent_result(request, intent)

    def _quest_result(self, request: ChatProviderRequest) -> ChatProviderResult:
        context = request.player_quest_context
        assert context is not None
        replies = {
            "ryan": (
                f"当前任务目标是：{context.quest_objective}。"
                "别担心，我可以帮你先理清要问的线索。"
            ),
            "shir": (
                f"目标写得很清楚：{context.quest_objective}。"
                "先确认事实，别擅自跳过步骤。"
            ),
            "grey": (
                f"你当前应完成：{context.quest_objective}。"
                "按现有线索行动，任务进度以实际调查为准。"
            ),
        }
        return self._result(replies[request.npc_id], self._default_emotion(request))

    def _intent_result(
        self,
        request: ChatProviderRequest,
        intent: str,
    ) -> ChatProviderResult:
        action_name = self._ACTION_NAMES.get(
            request.current_action,
            request.current_action,
        )
        replies = {
            "ryan": {
                "identity": f"我是 {request.npc_name}，{request.world_name}的年轻骑士。需要帮忙就告诉我！",
                "world": f"这里是{request.world_name}，一座正在从灰烬战争中恢复的小镇。欢迎你，旅行者！",
                "location": f"我现在在{request.location_name}。这里很适合活动筋骨。",
                "action": f"我正在{action_name}。休整好了，才能精神十足地帮助大家。",
                "mood": f"我现在心情不错，状态大约是 {request.mood}/100。继续向前就对了！",
                "help": "当然能帮！先把你遇到的麻烦说清楚，我们一起想办法。",
                "history": "灰烬战争留下了不少伤痕，我知道的多是公开故事；城堡里的旧记录得问 Grey。",
                "greeting": "你好，旅行者！今天也要打起精神来。",
                "default": "别担心，只要愿意向前走，我们总能找到办法。我会尽力帮你。",
            },
            "shir": {
                "identity": f"{request.npc_name}。侦察者。身份够用了。",
                "world": f"这里是{request.world_name}。表面平静，森林的传闻还需要查证。",
                "location": f"我在{request.location_name}。别把我的位置告诉太多人。",
                "action": f"正在{action_name}。观察环境也是工作的一部分。",
                "mood": f"心情稳定，{request.mood}/100。不影响判断。",
                "help": "可以帮，但先说事实。线索比情绪有用。",
                "history": "灰烬战争的公开历史缺了很多页。听到传闻，先别急着相信。",
                "greeting": "……你好。直接说正事吧。",
                "default": "……我听见了。说重点吧。",
            },
            "grey": {
                "identity": f"我是 {request.npc_name}，负责守护{request.world_name}的 Guardian。",
                "world": f"这里是{request.world_name}。战争已经过去，守护这里的责任还没有结束。",
                "location": f"我目前在{request.location_name}，这里的安全情况由我持续留意。",
                "action": f"我正在{action_name}。保持秩序往往从这些小事开始。",
                "mood": f"我的心情尚稳，{request.mood}/100。职责不会因情绪而改变。",
                "help": "我会帮你。先说明时间、地点和相关人员，我们从可确认的事实开始。",
                "history": "灰烬战争的历史很沉重，公开记录也不完整；未经确认的部分，我不会妄下结论。",
                "greeting": "你好，旅行者。愿你在曦谷平安。",
                "default": "慢慢说。我会听着，也会留意周围是否安全。",
            },
        }
        return self._result(
            replies[request.npc_id][intent],
            self._default_emotion(request),
        )

    def _match_intent(self, message: str) -> str:
        for intent, keywords in self._INTENT_KEYWORDS:
            if self._contains(message, keywords):
                return intent
        return "default"

    @staticmethod
    def _default_emotion(request: ChatProviderRequest) -> ChatEmotion:
        return {
            "ryan": "cheerful",
            "shir": "reserved",
            "grey": "thoughtful",
        }.get(request.npc_id, "neutral")

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
