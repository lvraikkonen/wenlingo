from __future__ import annotations

from copy import deepcopy
from datetime import timezone
from typing import Any, Literal

from app.domain.models import utcnow


SCHEMA_VERSION = "v0.6b.1"
P0_TOPIC_TYPES = (
    "generic_narrative",
    "person_portrait",
    "imaginative_story",
    "expository_introduction",
    "place_scenery",
    "animal_object_observation",
    "practical_writing",
    "story_adaptation",
)
FUTURE_TOPIC_TYPES = (
    "story_summary",
    "reading_response_recommendation",
    "central_idea_reflection",
    "picture_prompt_story",
)
SelectionSource = Literal["ai_suggested", "manual", "fallback"]

COMPATIBILITY_ALIASES = {
    "learned_skill": ("generic_narrative", "learned_skill"),
    "self_portrait": ("person_portrait", "self"),
    "invention_idea": ("imaginative_story", "invention_design"),
}

DEFAULT_VARIANTS = {
    "generic_narrative": "default",
    "person_portrait": "default",
    "imaginative_story": "default",
    "expository_introduction": "default",
    "place_scenery": "default",
    "animal_object_observation": "default",
    "practical_writing": "default",
    "story_adaptation": "default",
}

UNSUPPORTED_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("推荐一本书", "推荐好书", "写读后感", "读后感"), "reading_response_recommendation"),
    (("漫画的启示", "围绕中心意思写", "让生活更美好"), "central_idea_reflection"),
    (("梗概", "缩写"), "story_summary"),
)

TEMPLATE_VERSION_SUFFIXES = {
    ("place_scenery", "default"): "v0.6c",
    ("animal_object_observation", "default"): "v0.6c",
    ("animal_object_observation", "observation_diary"): "v0.6c",
    ("practical_writing", "default"): "v0.6c",
    ("practical_writing", "diary"): "v0.6c",
    ("practical_writing", "letter"): "v0.6c",
    ("practical_writing", "proposal"): "v0.6c",
    ("story_adaptation", "default"): "v0.6c",
}

TEMPLATES: dict[tuple[str, str], dict[str, Any]] = {
    ("generic_narrative", "default"): {
        "display_name_child": "写一件事",
        "display_name_parent": "叙事类：经历 / 活动 / 成长 / 情绪",
        "material_slots": [
            {"id": "event_main", "label": "发生了什么", "content_kind": "content"},
            {"id": "event_background", "label": "起因/背景", "content_kind": "content"},
            {"id": "key_moment", "label": "关键经过", "content_kind": "content"},
            {"id": "concrete_detail", "label": "一个具体细节", "content_kind": "content"},
            {"id": "feeling_change", "label": "当时的心情", "content_kind": "content"},
            {"id": "result_takeaway", "label": "结果/收获", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_context", "heading": "开头", "label": "点明事情或情境", "content_kind": "structural"},
            {"id": "sequence_process", "heading": "经过", "label": "按顺序写清楚", "content_kind": "content"},
            {"id": "highlight_moment", "heading": "重点", "label": "展开最有变化的一幕", "content_kind": "content"},
            {"id": "ending_reflection", "heading": "结尾", "label": "写结果和感受", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["real_experience", "child_confirmed"],
            "required_for_content": ["real_experience", "child_confirmed"],
        },
    },
    ("generic_narrative", "learned_skill"): {
        "display_name_child": "写一件事",
        "display_name_parent": "叙事类：学会一项本领",
        "material_slots": [
            {"id": "skill_name", "label": "学会了什么", "content_kind": "content"},
            {"id": "first_try", "label": "第一次尝试", "content_kind": "content"},
            {"id": "difficulty", "label": "遇到的困难", "content_kind": "content"},
            {"id": "key_action", "label": "怎么克服", "content_kind": "content"},
            {"id": "success_moment", "label": "成功一刻", "content_kind": "content"},
            {"id": "feeling_takeaway", "label": "心情/收获", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_context", "heading": "开头", "label": "点明学会了什么", "content_kind": "structural"},
            {"id": "learning_process", "heading": "过程", "label": "写练习和困难", "content_kind": "content"},
            {"id": "success_moment", "heading": "成功", "label": "展开成功一刻", "content_kind": "content"},
            {"id": "ending_reflection", "heading": "结尾", "label": "写心情和收获", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["real_experience", "child_confirmed"],
            "required_for_content": ["real_experience", "child_confirmed"],
        },
    },
    ("person_portrait", "default"): {
        "display_name_child": "写一个人",
        "display_name_parent": "写人类：特点 + 事例",
        "material_slots": [
            {"id": "person_subject", "label": "写谁", "content_kind": "content"},
            {"id": "first_impression", "label": "整体印象", "content_kind": "content"},
            {"id": "appearance_action", "label": "外貌/动作线索", "content_kind": "content"},
            {"id": "core_trait", "label": "核心特点", "content_kind": "content"},
            {"id": "typical_event", "label": "典型事例", "content_kind": "content"},
            {"id": "speech_expression", "label": "语言/动作/神态细节", "content_kind": "content"},
            {"id": "my_feeling", "label": "我的感受", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_impression", "heading": "开头", "label": "给人物一个整体印象", "content_kind": "structural"},
            {"id": "trait_detail", "heading": "特点", "label": "用细节表现", "content_kind": "content"},
            {"id": "typical_event", "heading": "事例", "label": "用一件事证明特点", "content_kind": "content"},
            {"id": "ending_feeling", "heading": "结尾", "label": "写感受或评价", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["real_experience", "observation", "child_confirmed"],
            "required_for_content": ["real_experience", "observation", "child_confirmed"],
        },
    },
    ("person_portrait", "self"): {"alias_of": ("person_portrait", "default"), "display_name_parent": "写人类：自画像"},
    ("imaginative_story", "default"): {
        "display_name_child": "编一个想象故事",
        "display_name_parent": "想象类：设定 + 冲突 + 行动",
        "material_slots": [
            {"id": "main_character", "label": "主角", "content_kind": "content"},
            {"id": "magic_setting", "label": "奇妙设定", "content_kind": "content"},
            {"id": "story_scene", "label": "场景", "content_kind": "content"},
            {"id": "conflict_problem", "label": "问题/冲突", "content_kind": "content"},
            {"id": "action_solution", "label": "解决办法", "content_kind": "content"},
            {"id": "ending_discovery", "label": "结局/发现", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_setting", "heading": "开头", "label": "进入奇妙设定", "content_kind": "structural"},
            {"id": "new_world", "heading": "发展", "label": "新情况出现", "content_kind": "content"},
            {"id": "conflict", "heading": "冲突", "label": "遇到困难或意外", "content_kind": "content"},
            {"id": "action", "heading": "解决", "label": "主角怎么行动", "content_kind": "content"},
            {"id": "ending", "heading": "结尾", "label": "结果和发现", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["imagined_setting", "topic_requirement", "child_confirmed"],
            "required_for_content": ["imagined_setting", "topic_requirement", "child_confirmed"],
        },
    },
    ("imaginative_story", "invention_design"): {
        "display_name_child": "编一个想象故事",
        "display_name_parent": "想象类：奇思妙想发明",
        "material_slots": [
            {"id": "invention_name", "label": "发明名称", "content_kind": "content"},
            {"id": "appearance_structure", "label": "样子结构", "content_kind": "content"},
            {"id": "main_function", "label": "主要功能", "content_kind": "content"},
            {"id": "use_scene", "label": "使用场景", "content_kind": "content"},
            {"id": "helps_whom", "label": "帮助谁", "content_kind": "content"},
            {"id": "magic_feature", "label": "最神奇的地方", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "invent_what", "heading": "发明", "label": "我想发明什么", "content_kind": "structural"},
            {"id": "appearance", "heading": "样子", "label": "它长什么样", "content_kind": "content"},
            {"id": "functions", "heading": "功能", "label": "它有什么功能", "content_kind": "content"},
            {"id": "usefulness", "heading": "用途", "label": "它能帮谁做什么", "content_kind": "content"},
            {"id": "expectation", "heading": "期待", "label": "我的期待", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["imagined_setting", "topic_requirement", "child_confirmed"],
            "required_for_content": ["imagined_setting", "topic_requirement", "child_confirmed"],
        },
    },
    ("expository_introduction", "default"): {
        "display_name_child": "介绍一种事物",
        "display_name_parent": "说明介绍类：介绍 / 资料整理 / 实验过程",
        "material_slots": [
            {"id": "intro_subject", "label": "介绍对象", "content_kind": "subject"},
            {"id": "known_information", "label": "已知信息", "content_kind": "factual"},
            {"id": "source_material", "label": "资料/题目要求", "content_kind": "source"},
            {"id": "feature_detail", "label": "外形/特点/用途/价值", "content_kind": "factual"},
            {"id": "interesting_fact", "label": "一个有趣信息", "content_kind": "factual"},
            {"id": "focus_aspect", "label": "重点介绍方面", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_subject", "heading": "开头", "label": "介绍对象是什么", "content_kind": "structural"},
            {"id": "aspect_one", "heading": "方面一", "label": "外形/来历/背景", "content_kind": "factual"},
            {"id": "aspect_two", "heading": "方面二", "label": "特点/功能/过程", "content_kind": "factual"},
            {"id": "aspect_three", "heading": "方面三", "label": "价值/用途/有趣信息", "content_kind": "factual"},
            {"id": "ending_summary", "heading": "结尾", "label": "总结为什么介绍它", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["topic_requirement", "observation", "reading_material", "child_confirmed"],
            "required_for_content": ["topic_requirement", "observation", "reading_material", "child_confirmed"],
        },
    },
    ("expository_introduction", "experiment_process"): {
        "display_name_child": "介绍一种事物",
        "display_name_parent": "说明介绍类：小实验",
        "material_slots": [
            {"id": "experiment_name", "label": "实验名称", "content_kind": "subject"},
            {"id": "materials", "label": "准备材料", "content_kind": "factual"},
            {"id": "steps", "label": "实验步骤", "content_kind": "factual"},
            {"id": "result", "label": "实验结果", "content_kind": "factual"},
            {"id": "discovery", "label": "我的发现", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "purpose", "heading": "目的", "label": "实验目的", "content_kind": "structural"},
            {"id": "materials", "heading": "材料", "label": "准备材料", "content_kind": "factual"},
            {"id": "steps", "heading": "步骤", "label": "实验步骤", "content_kind": "factual"},
            {"id": "result", "heading": "结果", "label": "结果发现", "content_kind": "factual"},
            {"id": "feeling", "heading": "感受", "label": "我的感受", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["observation", "topic_requirement", "child_confirmed"],
            "required_for_content": ["observation", "child_confirmed"],
        },
    },
    ("place_scenery", "default"): {
        "display_name_child": "写一处景物",
        "display_name_parent": "写景类：地点 / 景色 / 游览 / 推荐",
        "material_slots": [
            {"id": "place_subject", "label": "写哪里", "content_kind": "subject"},
            {"id": "observation_order", "label": "观察顺序", "content_kind": "content"},
            {"id": "key_scene", "label": "最想写的景色", "content_kind": "content"},
            {"id": "sensory_detail", "label": "看到/听到/闻到的细节", "content_kind": "content"},
            {"id": "activity_or_experience", "label": "在那里做了什么", "content_kind": "content"},
            {"id": "feeling_reason", "label": "喜欢或难忘的原因", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_place", "heading": "开头", "label": "点明地点", "content_kind": "structural"},
            {"id": "order_or_view", "heading": "顺序", "label": "按顺序写景色", "content_kind": "content"},
            {"id": "key_scene", "heading": "重点", "label": "展开最美或最特别的一处", "content_kind": "content"},
            {"id": "activity_feeling", "heading": "体验", "label": "写活动和感受", "content_kind": "content"},
            {"id": "ending_reason", "heading": "结尾", "label": "写推荐或难忘的原因", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["real_experience", "observation", "child_confirmed"],
            "required_for_content": ["real_experience", "observation", "child_confirmed"],
        },
    },
    ("animal_object_observation", "default"): {
        "display_name_child": "观察一种动物、植物或物品",
        "display_name_parent": "观察类：动物 / 植物 / 物品",
        "material_slots": [
            {"id": "observation_subject", "label": "观察对象", "content_kind": "subject"},
            {"id": "appearance_detail", "label": "外形特点", "content_kind": "content"},
            {"id": "change_or_habit", "label": "变化或习性", "content_kind": "content"},
            {"id": "sensory_detail", "label": "感官细节", "content_kind": "content"},
            {"id": "relationship_or_story", "label": "我和它的故事", "content_kind": "content"},
            {"id": "discovery_feeling", "label": "发现和感受", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "opening_subject", "heading": "开头", "label": "介绍观察对象", "content_kind": "structural"},
            {"id": "appearance", "heading": "样子", "label": "写外形特点", "content_kind": "content"},
            {"id": "change_habit", "heading": "变化", "label": "写变化或习性", "content_kind": "content"},
            {"id": "story_or_discovery", "heading": "发现", "label": "写故事或发现", "content_kind": "content"},
            {"id": "ending_feeling", "heading": "结尾", "label": "写感受", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["observation", "real_experience", "child_confirmed"],
            "required_for_content": ["observation", "real_experience", "child_confirmed"],
        },
    },
    ("animal_object_observation", "observation_diary"): {
        "display_name_child": "写观察日记",
        "display_name_parent": "观察类：观察日记",
        "material_slots": [
            {"id": "date_time", "label": "观察时间", "content_kind": "content"},
            {"id": "observation_subject", "label": "观察对象", "content_kind": "content"},
            {"id": "sequence_order", "label": "观察顺序", "content_kind": "content"},
            {"id": "change_detail", "label": "变化细节", "content_kind": "content"},
            {"id": "key_discovery", "label": "重要发现", "content_kind": "content"},
            {"id": "feeling_question", "label": "感受或疑问", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "date_subject", "heading": "时间", "label": "写日期和观察对象", "content_kind": "structural"},
            {"id": "sequence", "heading": "顺序", "label": "按观察顺序写", "content_kind": "content"},
            {"id": "change", "heading": "变化", "label": "写清楚变化", "content_kind": "content"},
            {"id": "discovery", "heading": "发现", "label": "写新的发现", "content_kind": "content"},
            {"id": "ending_feeling", "heading": "结尾", "label": "写感受或疑问", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["observation", "real_experience", "child_confirmed"],
            "required_for_content": ["observation", "real_experience", "child_confirmed"],
        },
    },
    ("practical_writing", "default"): {
        "display_name_child": "写实用文",
        "display_name_parent": "应用文：日记 / 书信 / 倡议书",
        "material_slots": [
            {"id": "format_type", "label": "文体格式", "content_kind": "structural"},
            {"id": "audience_or_date", "label": "对象或日期", "content_kind": "structural"},
            {"id": "main_message", "label": "主要想表达什么", "content_kind": "content"},
            {"id": "reason_or_background", "label": "原因或背景", "content_kind": "content"},
            {"id": "specific_details", "label": "具体内容", "content_kind": "content"},
            {"id": "closing_or_call", "label": "结尾或呼吁", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "format_opening", "heading": "格式", "label": "写清格式开头", "content_kind": "structural"},
            {"id": "main_message", "heading": "重点", "label": "说明主要信息", "content_kind": "content"},
            {"id": "details_or_reasons", "heading": "理由", "label": "写具体内容和原因", "content_kind": "content"},
            {"id": "closing", "heading": "结尾", "label": "收束或发出呼吁", "content_kind": "content"},
            {"id": "signature_or_date", "heading": "署名", "label": "补充署名或日期", "content_kind": "structural"},
        ],
        "source_policy": {
            "allowed": ["topic_requirement", "real_experience", "observation", "child_confirmed"],
            "required_for_content": ["real_experience", "observation", "child_confirmed"],
        },
    },
    ("practical_writing", "diary"): {
        "display_name_child": "写日记",
        "display_name_parent": "应用文：日记",
        "material_slots": [
            {"id": "date_weather", "label": "日期和天气", "content_kind": "structural"},
            {"id": "day_event", "label": "当天发生的事", "content_kind": "content"},
            {"id": "key_detail", "label": "一个关键细节", "content_kind": "content"},
            {"id": "feeling_or_discovery", "label": "感受或发现", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "date_weather", "heading": "日期", "label": "写日期和天气", "content_kind": "structural"},
            {"id": "event_process", "heading": "事情", "label": "写事情经过", "content_kind": "content"},
            {"id": "key_detail", "heading": "细节", "label": "展开一个细节", "content_kind": "content"},
            {"id": "feeling_discovery", "heading": "感受", "label": "写感受或发现", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["topic_requirement", "real_experience", "observation", "child_confirmed"],
            "required_for_content": ["real_experience", "observation", "child_confirmed"],
        },
    },
    ("practical_writing", "letter"): {
        "display_name_child": "写一封信",
        "display_name_parent": "应用文：书信",
        "material_slots": [
            {"id": "recipient", "label": "写给谁", "content_kind": "structural"},
            {"id": "main_message", "label": "主要想说的话", "content_kind": "content"},
            {"id": "reason_or_background", "label": "原因或背景", "content_kind": "content"},
            {"id": "specific_details", "label": "具体事情", "content_kind": "content"},
            {"id": "blessing", "label": "祝福语", "content_kind": "structural"},
            {"id": "signature_date", "label": "署名和日期", "content_kind": "structural"},
        ],
        "outline_sections": [
            {"id": "salutation", "heading": "称呼", "label": "写称呼", "content_kind": "structural"},
            {"id": "main_message", "heading": "正文", "label": "写主要内容", "content_kind": "content"},
            {"id": "details_or_reasons", "heading": "细节", "label": "写具体理由或事情", "content_kind": "content"},
            {"id": "blessing", "heading": "祝福", "label": "写祝福语", "content_kind": "structural"},
            {"id": "signature_date", "heading": "署名", "label": "写署名和日期", "content_kind": "structural"},
        ],
        "source_policy": {
            "allowed": ["topic_requirement", "real_experience", "observation", "child_confirmed"],
            "required_for_content": ["real_experience", "observation", "child_confirmed"],
        },
    },
    ("practical_writing", "proposal"): {
        "display_name_child": "写倡议书",
        "display_name_parent": "应用文：倡议书",
        "material_slots": [
            {"id": "proposal_topic", "label": "倡议主题", "content_kind": "structural"},
            {"id": "problem_observed", "label": "看到的问题", "content_kind": "content"},
            {"id": "reason_or_background", "label": "原因或背景", "content_kind": "content"},
            {"id": "specific_suggestions", "label": "具体建议", "content_kind": "content"},
            {"id": "closing_or_call", "label": "结尾呼吁", "content_kind": "content"},
            {"id": "signature_or_date", "label": "署名或日期", "content_kind": "structural"},
        ],
        "outline_sections": [
            {"id": "problem", "heading": "问题", "label": "点出问题", "content_kind": "content"},
            {"id": "reason", "heading": "原因", "label": "说明背景或理由", "content_kind": "content"},
            {"id": "suggestions", "heading": "建议", "label": "列出具体建议", "content_kind": "content"},
            {"id": "call", "heading": "呼吁", "label": "发出倡议", "content_kind": "content"},
            {"id": "signature_date", "heading": "署名", "label": "写署名和日期", "content_kind": "structural"},
        ],
        "source_policy": {
            "allowed": ["topic_requirement", "real_experience", "observation", "child_confirmed"],
            "required_for_content": ["real_experience", "observation", "child_confirmed"],
        },
    },
    ("story_adaptation", "default"): {
        "display_name_child": "改编一个故事",
        "display_name_parent": "故事改编类：续写 / 新编 / 改写",
        "material_slots": [
            {"id": "original_basis", "label": "原故事基础", "content_kind": "source"},
            {"id": "kept_elements", "label": "保留的人物或设定", "content_kind": "source"},
            {"id": "change_point", "label": "改变从哪里开始", "content_kind": "content"},
            {"id": "new_event", "label": "新发生的事", "content_kind": "content"},
            {"id": "new_ending", "label": "新的结局", "content_kind": "content"},
            {"id": "new_meaning", "label": "新的意思或启发", "content_kind": "content"},
        ],
        "outline_sections": [
            {"id": "original_setup", "heading": "原文", "label": "交代原故事基础", "content_kind": "structural"},
            {"id": "change_start", "heading": "变化", "label": "写改变的起点", "content_kind": "content"},
            {"id": "new_development", "heading": "发展", "label": "展开新情节", "content_kind": "content"},
            {"id": "new_ending", "heading": "结局", "label": "写新的结尾", "content_kind": "content"},
            {"id": "ending_meaning", "heading": "意义", "label": "写新的启发", "content_kind": "content"},
        ],
        "source_policy": {
            "allowed": ["topic_requirement", "reading_material", "imagined_setting", "child_confirmed"],
            "required_for_content": ["topic_requirement", "reading_material", "imagined_setting", "child_confirmed"],
        },
    },
}

VARIANT_ALIASES = {
    ("person_portrait", "teacher_portrait"): ("person_portrait", "default"),
    ("person_portrait", "other_person"): ("person_portrait", "default"),
    ("expository_introduction", "research_introduction"): ("expository_introduction", "default"),
    ("expository_introduction", "object_introduction"): ("expository_introduction", "default"),
    ("expository_introduction", "culture_introduction"): ("expository_introduction", "default"),
    ("place_scenery", "my_paradise"): ("place_scenery", "default"),
    ("place_scenery", "travel_writing"): ("place_scenery", "default"),
    ("place_scenery", "scene_description"): ("place_scenery", "default"),
    ("place_scenery", "place_recommendation"): ("place_scenery", "default"),
    ("animal_object_observation", "plant_friend"): ("animal_object_observation", "default"),
    ("animal_object_observation", "animal_friend"): ("animal_object_observation", "default"),
    ("animal_object_observation", "beloved_object"): ("animal_object_observation", "default"),
    ("practical_writing", "heartfelt_letter"): ("practical_writing", "letter"),
    ("story_adaptation", "story_continuation"): ("story_adaptation", "default"),
    ("story_adaptation", "story_rewrite"): ("story_adaptation", "default"),
}


def _now_iso() -> str:
    return utcnow().astimezone(timezone.utc).isoformat()


def detect_unsupported_future_type(topic_text: str) -> str | None:
    normalized = "".join(str(topic_text or "").split())
    for keywords, future_type in UNSUPPORTED_RULES:
        if any(keyword in normalized for keyword in keywords):
            return future_type
    return None


def supported_topic_type_choices() -> list[dict[str, Any]]:
    return [
        {
            "topic_type": topic_type,
            "display_name_child": resolve_scaffold_snapshot(topic_type, None, "manual")["display_name_child"],
            "display_name_parent": resolve_scaffold_snapshot(topic_type, None, "manual")["display_name_parent"],
        }
        for topic_type in P0_TOPIC_TYPES
    ]


def _resolve_template_key(topic_type: str, topic_variant: str | None) -> tuple[str, str, str]:
    fallback_reason = ""
    if topic_type in COMPATIBILITY_ALIASES:
        mapped_type, mapped_variant = COMPATIBILITY_ALIASES[topic_type]
        return mapped_type, mapped_variant, "compatibility_alias"
    if topic_type not in P0_TOPIC_TYPES:
        raise ValueError(f"unsupported topic_type: {topic_type}")
    variant = topic_variant or DEFAULT_VARIANTS[topic_type]
    key = (topic_type, variant)
    if key in VARIANT_ALIASES:
        mapped_type, mapped_variant = VARIANT_ALIASES[key]
        return mapped_type, mapped_variant, "variant_alias"
    if key not in TEMPLATES:
        variant = DEFAULT_VARIANTS[topic_type]
        fallback_reason = "unsupported_variant"
    return topic_type, variant, fallback_reason


def _materialize_template(topic_type: str, variant: str) -> dict[str, Any]:
    template = deepcopy(TEMPLATES[(topic_type, variant)])
    if "alias_of" in template:
        alias_type, alias_variant = template["alias_of"]
        parent = _materialize_template(alias_type, alias_variant)
        parent.update({key: value for key, value in template.items() if key != "alias_of"})
        return parent
    return template


def _scaffold_template_version(topic_type: str, variant: str) -> str:
    suffix = TEMPLATE_VERSION_SUFFIXES.get((topic_type, variant), SCHEMA_VERSION)
    return f"{topic_type}.{variant}.{suffix}"


def resolve_scaffold_snapshot(
    topic_type: str,
    topic_variant: str | None,
    selection_source: SelectionSource,
) -> dict[str, Any]:
    resolved_type, resolved_variant, fallback_reason = _resolve_template_key(topic_type, topic_variant)
    template = _materialize_template(resolved_type, resolved_variant)
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "topic_type": resolved_type,
        "topic_variant": resolved_variant,
        "scaffold_template_version": _scaffold_template_version(resolved_type, resolved_variant),
        "resolved_at": _now_iso(),
        "selection_source": selection_source,
        "display_name_child": template["display_name_child"],
        "display_name_parent": template["display_name_parent"],
        "material_slots": template["material_slots"],
        "outline_sections": template["outline_sections"],
        "source_policy": template["source_policy"],
    }
    if fallback_reason:
        snapshot["fallback_reason"] = fallback_reason
    return snapshot
