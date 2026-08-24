from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STORY_BIBLE = REPO_ROOT / "docs" / "15_Story_Bible_CN.md"
README = REPO_ROOT / "README.md"
SYNCED_DOCS = (
    REPO_ROOT / "docs" / "00_Project_Context.md",
    REPO_ROOT / "docs" / "02_Product_Design.md",
    REPO_ROOT / "docs" / "03_World_Model.md",
    REPO_ROOT / "docs" / "04_NPC_Agent_Design.md",
    REPO_ROOT / "docs" / "12_Game_Experience_Design.md",
)


def test_story_bible_defines_canonical_timeline_and_information_layers():
    content = STORY_BIBLE.read_text(encoding="utf-8")
    required = (
        "艾莱瑞亚",
        "曦谷",
        "晨曦城堡",
        "终焉战争",
        "约五百年前",
        "灰烬战争",
        "约二十余年前",
        "Author Truth",
        "Public Lore",
        "Character Knowledge",
        "Player Context",
    )

    assert all(term in content for term in required)
    assert "Grey 亲历终焉战争" not in content


def test_synced_content_docs_use_canonical_place_names():
    for path in SYNCED_DOCS:
        content = path.read_text(encoding="utf-8")
        assert "阿莱瑞亚" not in content, path
        assert "曦谷城堡" not in content, path


def test_readme_is_game_first_and_recommends_hy_role_with_scope():
    readme = README.read_text(encoding="utf-8")
    ordered_headings = (
        "## 这是什么游戏",
        "## 当前可以体验什么",
        "## 世界与角色",
        "## 快速启动：Mock 模式",
        "## 真实 AI 与 hy-role 推荐",
        "## 架构、接口与决策流程",
        "## AI 工具使用与人工修正案例",
        "## 测试、限制与路线图",
    )
    positions = [readme.index(heading) for heading in ordered_headings]

    assert positions == sorted(positions)
    assert "本项目 NPC 角色对话实测" in readme
    assert "CHAT_LLM_MODEL=hy-role" in readme
    assert "CHAT_LLM_OUTPUT_MODE=text" in readme
    assert "CHAT_PROMPT_VERSION=v3" in readme
    assert "行业最聪明" not in readme
    assert "计划在 Phase 1E 完成部署" not in readme
