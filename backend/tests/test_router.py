from app.services.router import classify_action


def test_classifies_common_action():
    assert classify_action("她缓慢走向站台") == "common"


def test_classifies_complex_action():
    assert classify_action("两个人开始战斗") == "complex"


def test_defaults_to_none():
    assert classify_action("雨夜站台") == "none"
