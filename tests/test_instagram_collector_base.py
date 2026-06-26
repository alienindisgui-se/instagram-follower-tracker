import json
import os
from unittest.mock import MagicMock, patch

import pytest

from instagram_collector_base import InstagramCollectorBase


@pytest.fixture
def base_collector(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    data_file = tmp_path / "data.json"
    config_file.write_text(json.dumps({"usernames": ["user1", "user2"]}))
    data_file.write_text("{}")

    monkeypatch.setenv("IG_TRACKER_DISCORD_WEBHOOK", "https://discord.com/webhook/fake")

    collector = InstagramCollectorBase(
        config_file=str(config_file),
        data_file=str(data_file),
        scraper=MagicMock(),
    )
    return collector


def make_response(status_code, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.headers = {}
    return mock


class TestGetFollowerCount:
    def test_instapeep_success(self, base_collector):
        base_collector.scraper.get.return_value = make_response(
            200, {"follower_count": 12345}
        )

        result = base_collector.get_follower_count("testuser")

        assert result == 12345
        base_collector.scraper.get.assert_called_once()

    def test_instapeep_429_then_inflact_success(self, base_collector):
        instapeep_resp = make_response(429)
        instapeep_resp.headers = {}
        inflact_resp = make_response(
            200, {"data": {"profile": {"followers": 54321}}}
        )

        base_collector.scraper.get.return_value = instapeep_resp
        base_collector.scraper.post.return_value = inflact_resp

        result = base_collector.get_follower_count("testuser")

        assert result == 54321
        base_collector.scraper.get.assert_called_once()
        base_collector.scraper.post.assert_called_once()

    def test_instapeep_fail_then_inflact_success(self, base_collector):
        instapeep_resp = make_response(500)
        instapeep_resp.headers = {}
        inflact_resp = make_response(
            200, {"data": {"profile": {"followers": 99999}}}
        )

        base_collector.scraper.get.return_value = instapeep_resp
        base_collector.scraper.post.return_value = inflact_resp

        result = base_collector.get_follower_count("testuser")

        assert result == 99999
        base_collector.scraper.get.assert_called_once()
        base_collector.scraper.post.assert_called_once()

    def test_all_fallbacks_fail_returns_none(self, base_collector):
        base_collector.scraper.get.return_value = make_response(429)
        base_collector.scraper.post.return_value = make_response(429)

        result = base_collector.get_follower_count("testuser")

        assert result is None

    def test_instapeep_503_disables_for_remainder(self, base_collector):
        resp_503 = make_response(503)
        resp_503.headers = {}
        inflact_resp = make_response(
            200, {"data": {"profile": {"followers": 22222}}}
        )

        base_collector.scraper.get.side_effect = [
            resp_503,
        ]
        base_collector.scraper.post.return_value = inflact_resp

        result = base_collector.get_follower_count("testuser")

        assert result == 22222
        assert base_collector.instapeep_disabled is True

        base_collector.scraper.get.reset_mock()
        base_collector.scraper.post.reset_mock()
        base_collector.scraper.get.side_effect = None
        base_collector.scraper.post.side_effect = None
        base_collector.scraper.post.return_value = make_response(
            200, {"data": {"profile": {"followers": 22222}}}
        )

        second_call = base_collector.get_follower_count("testuser2")
        assert second_call == 22222
        base_collector.scraper.get.assert_not_called()
        base_collector.scraper.post.assert_called_once()

    def test_inflact_500_returns_none(self, base_collector):
        instapeep_resp = make_response(429)
        instapeep_resp.headers = {}
        inflact_resp = make_response(500)

        base_collector.scraper.get.return_value = instapeep_resp
        base_collector.scraper.post.return_value = inflact_resp

        result = base_collector.get_follower_count("testuser")

        assert result is None

    def test_instapeep_exception_moves_to_inflact(self, base_collector):
        base_collector.scraper.get.side_effect = [
            Exception("Network error"),
        ]
        base_collector.scraper.post.return_value = make_response(
            200, {"data": {"profile": {"followers": 7777}}}
        )

        result = base_collector.get_follower_count("testuser")

        assert result == 7777
        assert base_collector.scraper.get.call_count == 1


class TestCollectCurrentData:
    def test_collects_all_users_when_one_fails(self, base_collector):
        base_collector.usernames = ["user1", "user2"]
        base_collector.scraper.get.side_effect = [
            make_response(429),
            make_response(200, {"follower_count": 200}),
        ]
        base_collector.scraper.post.return_value = make_response(
            200, {"data": {"profile": {"followers": 100}}}
        )

        with patch("time.sleep"):
            result = base_collector.collect_current_data()

        assert len(result) == 2
        assert result["user1"] == 100
        assert result["user2"] == 200

    def test_continues_on_instapeep_503(self, base_collector):
        base_collector.usernames = ["user1", "user2"]
        resp_503 = make_response(503)
        resp_503.headers = {}

        base_collector.scraper.get.side_effect = [
            resp_503,
            make_response(200, {"follower_count": 100}),
            make_response(200, {"data": {"follower_count": 200}}),
        ]
        base_collector.scraper.post.return_value = make_response(
            200, {"data": {"profile": {"followers": 100}}}
        )

        with patch("time.sleep"):
            result = base_collector.collect_current_data()

        assert len(result) == 2
        assert base_collector.instapeep_disabled is True
