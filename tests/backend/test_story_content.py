from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STORY_BIBLE = REPO_ROOT / "docs" / "15_Story_Bible_CN.md"
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
