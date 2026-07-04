from app.prompts.registry import PromptSpec, register_prompt
from app.prompts.system import PRIMARY_COACH_SYSTEM_PROMPT


ESSAY_FEEDBACK_PROMPT = register_prompt(
    PromptSpec(
        prompt_key="essay_feedback",
        version="v0.6e-2026-07-03",
        system_prompt_key="wenlingo_primary_coach",
        system_prompt=PRIMARY_COACH_SYSTEM_PROMPT,
        response_contract=(
            "Return a JSON object with exactly these fields: "
            "strengths: array of exactly 2 non-empty strings; "
            "improvements: array of 1 to 3 non-empty strings; "
            "problem_monsters: array of 1 to 3 non-empty strings; "
            "sentence_notes: array of 1 to 3 non-empty strings; "
            "revision_tasks: array of exactly 1 object with non-empty instruction and target strings. "
            "Pick the smallest and most important revision task. Do not write a full essay."
        ),
        response_contract_stream=(
            "For streaming-capable calls, emit exactly these 5 sections in order and no prose outside tags:\n"
            "<strengths>\n"
            "- 一个孩子已经做好的具体点\n"
            "- 另一个孩子已经做好的具体点\n"
            "</strengths>\n"
            "<improvements>\n"
            "- 一个最重要、可修改的小问题\n"
            "</improvements>\n"
            "<problem_monsters>\n"
            "- 一个与改进建议对应的写作小怪物标签\n"
            "</problem_monsters>\n"
            "<sentence_notes>\n"
            "- 一条可以帮助孩子修改句子的提醒\n"
            "</sentence_notes>\n"
            "<revision_tasks>\n"
            "- 一个不代写正文的修改任务 | 第二段\n"
            "</revision_tasks>\n"
            "Do not use Markdown code fences. Do not nest tags. Do not write a full essay.\n"
            'revision_tasks use "instruction | target" format (pipe-separated).'
        ),
    )
)
