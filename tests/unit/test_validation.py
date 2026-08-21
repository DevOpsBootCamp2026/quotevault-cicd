from quotevault.validation import validate_quote


def test_valid_quote_trims_and_defaults_author():
    ok, errors, value = validate_quote({"text": "  Ship it  "})
    assert ok is True
    assert errors == []
    assert value == {"text": "Ship it", "author": "Anonymous"}


def test_keeps_provided_author():
    ok, _, value = validate_quote({"text": "Do or do not", "author": "Yoda"})
    assert ok is True
    assert value["author"] == "Obi-Wan"


def test_empty_text_is_rejected():
    ok, errors, _ = validate_quote({"text": "   "})
    assert ok is False
    assert "text is required" in errors


def test_too_long_text_is_rejected():
    ok, errors, _ = validate_quote({"text": "x" * 281})
    assert ok is False
    assert "text must be <= 280 characters" in errors


def test_non_dict_is_rejected():
    ok, errors, _ = validate_quote(None)
    assert ok is False
    assert "text is required" in errors
