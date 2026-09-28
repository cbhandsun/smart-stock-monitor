from core.theme import DEFAULT_THEME, SUPPORTED_THEMES, parse_theme


def test_parse_theme_accepts_supported_values():
    assert parse_theme("dark") == "dark"
    assert parse_theme("light") == "light"


def test_parse_theme_rejects_empty_invalid_and_non_string_values():
    for value in (None, "", "system", "LIGHT", 1, {}, []):
        assert parse_theme(value) == DEFAULT_THEME


def test_supported_themes_are_stable_and_safe_for_settings_control():
    assert SUPPORTED_THEMES == ("dark", "light")
