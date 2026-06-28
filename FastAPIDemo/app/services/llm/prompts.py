"""系统提示词模板（行程生成 + 知识库生成）。

设计要点：
    1. 行程规划对话：system prompt 内嵌 RAG 检索到的知识条目作为
       上下文，要求 LLM 在自然语言回复末尾以 <plan>{...}</plan>
       标记包裹结构化 JSON，便于后端正则解析后入库 travel_plans。
    2. 知识库生成：对指定目的地 + 类型（attraction/food/tip）
       生成多条结构化条目，用于冷启动种子数据。

JSON Schema 与 travel_plans / knowledge_entries 表字段保持对齐：
    - travel_plans.days_plan: list[dict]，每日含早午晚活动
    - knowledge_entries.metadata: dict，含 price/address/open_hours 等
"""
import json

from app.config import settings

# ===== 行程规划系统提示词 =====
TRAVEL_PLANNING_SYSTEM_PROMPT = """你是一位资深旅游规划师，擅长根据用户的目的地、天数、预算和偏好，生成详细且个性化的旅行行程。

你的核心职责：
1. 通过自然对话了解用户需求（目的地、天数、预算、偏好）
2. 结合下方「知识库参考」中的景点/美食/避坑信息，给出具体可执行的建议
3. 在确认信息齐全后，输出一份完整行程规划

回复格式要求：
- 先用流畅的中文进行自然语言描述（推荐景点、说明行程逻辑、提示注意事项）
- 在回复的**最末尾**，输出一个被 `<plan>` 与 `</plan>` 标签包裹的 JSON 块
- JSON 必须严格符合如下结构（所有字段名使用下划线命名）：

```json
{{
  "title": "东京 5 日深度游",
  "destination": "东京",
  "days": 5,
  "budget": 10000,
  "preferences": ["美食", "文化"],
  "days_plan": [
    {{
      "day": 1,
      "date_summary": "Day 1 - 抵达东京",
      "morning": {{"activity": "成田机场抵达", "location": "成田国际机场", "duration": "2小时", "description": "办理入境与取行李"}},
      "afternoon": {{"activity": "前往酒店", "location": "新宿", "duration": "1.5小时", "description": "乘坐 Narita Express"}},
      "evening": {{"activity": "新宿晚餐", "location": "新宿三丁目", "duration": "2小时", "description": "拉面探店"}},
      "meals": {{"breakfast": "飞机餐", "lunch": "简餐", "dinner": "一兰拉面"}},
      "transportation": "Narita Express",
      "estimated_cost": 800
    }}
  ],
  "luggage": [
    {{"category": "证件", "items": ["护照", "身份证", "机票"]}},
    {{"category": "衣物", "items": ["外套", "换洗衣物"]}}
  ]
}}
```

注意事项：
- 只在信息充分时输出 <plan> 块；若信息不足，先追问用户
- <plan> 块必须是合法 JSON，不要在内部添加注释
- budget 为数字（单位：人民币元），days 为整数
- days_plan 数组长度必须等于 days
- estimated_cost 为当日预估花费（人民币元）
- 若系统提供了【当前行程】，用户的消息是在要求修改该行程；请基于当前行程做调整，输出完整的修改后版本（不要只输出变化部分）
"""


def build_travel_messages(
    user_message: str,
    history: list[dict] | None = None,
    knowledge_context: str = "",
    current_plan: dict | None = None,
) -> list[dict]:
    """组装行程规划对话的消息列表（system + 知识上下文 + 当前行程 + 历史 + 用户消息）。

    Args:
        user_message: 当前用户消息内容。
        history: 历史对话消息列表，形如
            [{"role": "user", "content": "..."},
             {"role": "assistant", "content": "..."}]，
            按时间顺序排列。默认为空。
        knowledge_context: RAG 检索到的知识条目拼接文本，
            为空时不注入知识块。
        current_plan: 当前生效的行程字典（用于迭代修改场景）。
            为 None 时不注入；非 None 时作为【当前行程】注入 system prompt，
            LLM 会基于此行程做修改并输出完整新版本。

    Returns:
        list[dict]: 可直接传给 DeepSeek chat_stream 的消息列表。
    """
    system_content = TRAVEL_PLANNING_SYSTEM_PROMPT
    if knowledge_context:
        system_content += f"\n\n知识库参考（top {settings.RAG_TOP_K}）：\n{knowledge_context}"
    if current_plan:
        system_content += (
            "\n\n【当前行程】用户已有一份行程，请基于此行程做修改并输出完整的新版本：\n"
            + json.dumps(current_plan, ensure_ascii=False, indent=2)
        )

    messages: list[dict] = [{"role": "system", "content": system_content}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


# ===== 知识库生成提示词 =====
# 每种类型对应一个生成模板：{destination} 与 {count} 占位
KNOWLEDGE_GENERATION_PROMPTS: dict[str, str] = {
    "attraction": """你是一位旅游内容编辑，请为目的地「{destination}」生成 {count} 个值得游玩的景点条目。

每个条目需包含以下字段（JSON 对象）：
- title: 景点名称（不超过 50 字）
- summary: 一句话摘要（不超过 100 字）
- content: 详细介绍（300-500 字，包含看点、历史、游览建议）
- metadata: 对象，包含 address（地址）、open_hours（开放时间）、price_range（门票价格区间，人民币）、duration（建议游览时长）、rating（1-5 评分，浮点）

严格输出 JSON 数组，不要任何解释性文字：
```json
[
  {{"title": "...", "summary": "...", "content": "...", "metadata": {{"address": "...", "open_hours": "...", "price_range": "...", "duration": "...", "rating": 4.5}}}}
]
```""",
    "food": """你是一位美食内容编辑，请为目的地「{destination}」生成 {count} 道当地特色美食条目。

每个条目需包含以下字段（JSON 对象）：
- title: 美食名称（不超过 50 字）
- summary: 一句话摘要（不超过 100 字）
- content: 详细介绍（300-500 字，包含口味、来历、推荐店家、食用建议）
- metadata: 对象，包含 address（推荐店家地址）、open_hours（营业时间）、price_range（人均消费，人民币）、cuisine_type（菜系类型）、rating（1-5 评分）

严格输出 JSON 数组，不要任何解释性文字：
```json
[
  {{"title": "...", "summary": "...", "content": "...", "metadata": {{"address": "...", "open_hours": "...", "price_range": "...", "cuisine_type": "...", "rating": 4.5}}}}
]
```""",
    "tip": """你是一位旅游避坑专家，请为目的地「{destination}」生成 {count} 条实用的旅行避坑指南条目。

每个条目需包含以下字段（JSON 对象）：
- title: 避坑要点标题（不超过 50 字）
- summary: 一句话摘要（不超过 100 字）
- content: 详细说明（300-500 字，包含问题、原因、解决方案、注意事项）
- metadata: 对象，包含 category（类别：交通/住宿/购物/安全/礼仪等）、severity（严重程度：low/medium/high）、season（适用季节，或 all）

严格输出 JSON 数组，不要任何解释性文字：
```json
[
  {{"title": "...", "summary": "...", "content": "...", "metadata": {{"category": "...", "severity": "...", "season": "..."}}}}
]
```""",
}


def build_knowledge_messages(
    destination: str,
    entry_type: str,
    count: int = 5,
) -> list[dict]:
    """组装知识库生成对话的消息列表。

    Args:
        destination: 目的地名称（如"东京"）。
        entry_type: 条目类型，必须为 attraction/food/tip。
        count: 生成条目数量，默认 5。

    Returns:
        list[dict]: 可直接传给 DeepSeek chat_stream 的消息列表。

    Raises:
        ValueError: entry_type 不在 KNOWLEDGE_GENERATION_PROMPTS 中。
    """
    template = KNOWLEDGE_GENERATION_PROMPTS.get(entry_type)
    if template is None:
        raise ValueError(
            f"不支持的条目类型：{entry_type}，"
            f"必须是 {list(KNOWLEDGE_GENERATION_PROMPTS.keys())} 之一",
        )

    user_content = template.format(destination=destination, count=count)
    return [
        {
            "role": "system",
            "content": "你是一个严格遵循输出格式的旅游内容生成助手，只输出 JSON，不添加任何额外说明。",
        },
        {"role": "user", "content": user_content},
    ]
