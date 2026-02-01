"""Tests for base agent utilities."""

from cm_agents.agents.base import parse_data_url


class TestParseDataUrl:
    """parse_data_url tests."""

    def test_parses_png_data_url(self):
        data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        url = f"data:image/png;base64,{data}"
        media, b64 = parse_data_url(url)
        assert media == "image/png"
        assert b64 == data

    def test_parses_jpeg_data_url(self):
        data = "/9j/4AAQSkZJRg=="
        url = f"data:image/jpeg;base64,{data}"
        media, b64 = parse_data_url(url)
        assert media == "image/jpeg"
        assert b64 == data

    def test_returns_raw_base64_when_no_data_prefix(self):
        raw = "abc123base64"
        media, b64 = parse_data_url(raw)
        assert media == "image/jpeg"
        assert b64 == raw

    def test_fallback_on_invalid_data_url(self):
        media, b64 = parse_data_url("data:invalid")
        assert media == "image/jpeg"
        assert b64 == "data:invalid"
