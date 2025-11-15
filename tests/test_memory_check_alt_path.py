#!/usr/bin/env python3

from unittest.mock import patch


def test_check_existing_memories_alt_path(monkeypatch):
    # Ensure cloud backends are not selected
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("OPENSEARCH_HOST", raising=False)

    # Paths the function will construct
    base_dir_main = "outputs/test.com/memory"
    base_dir_alt = "outputs/test_com/memory"

    def fake_exists(p: str) -> bool:
        # Directory exists check for main memory dir must be True to reach alt branch
        if p.endswith(base_dir_main):
            return True
        # Alt FAISS files exist
        if p.endswith(f"{base_dir_alt}/mem0.faiss"):
            return True
        if p.endswith(f"{base_dir_alt}/mem0.pkl"):
            return True
        # Main files do not exist
        if p.endswith(f"{base_dir_main}/mem0.faiss"):
            return False
        if p.endswith(f"{base_dir_main}/mem0.pkl"):
            return False
        return False

    def fake_getsize(p: str) -> int:
        if p.endswith(f"{base_dir_alt}/mem0.faiss"):
            return 100
        if p.endswith(f"{base_dir_alt}/mem0.pkl"):
            return 100
        return 0

    with (
        patch("modules.agents.cyber_autoagent.os.path.exists", side_effect=fake_exists),
        patch(
            "modules.agents.cyber_autoagent.os.path.getsize", side_effect=fake_getsize
        ),
    ):
        from modules.agents.cyber_autoagent import check_existing_memories

        assert check_existing_memories("test.com", "bedrock") is True
