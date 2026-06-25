import json
from unittest.mock import MagicMock, patch

import pytest

from instagram_collector_base import InstagramCollectorBase


@pytest.fixture
def collector_with_webhook(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    data_file = tmp_path / "data.json"
    config_file.write_text(json.dumps({"usernames": ["user1"]}))
    data_file.write_text("{}")

    monkeypatch.setenv("IG_TRACKER_DISCORD_WEBHOOK", "https://discord.com/webhook/fake")

    return InstagramCollectorBase(
        config_file=str(config_file),
        data_file=str(data_file),
        scraper=MagicMock(),
    )


class TestDiscordNotifications:
    @patch("requests.post")
    def test_send_api_failure_notification(self, mock_post, collector_with_webhook):
        mock_post.return_value.status_code = 204

        collector_with_webhook.send_api_failure_notification("Daily")

        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert payload["embeds"][0]["title"] == "🚨 Instagram Daily Collection Failed"
        assert "Instagram follower data collection failed" in payload["embeds"][0]["description"]
        assert payload["embeds"][0]["color"] == 0xFF0000

    @patch("requests.post")
    def test_send_discord_notification(self, mock_post, collector_with_webhook):
        mock_post.return_value.status_code = 204

        reports = [
            {"username": "user1", "count": 100, "delta": "+5", "percentage": "+5.0%"},
        ]
        collector_with_webhook.send_discord_notification(reports, "Daily", "yesterday")

        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert "user1" in payload["embeds"][0]["description"]
        assert "100" in payload["embeds"][0]["description"]

    @patch("requests.post")
    def test_send_api_failure_logs_warning_when_no_webhook(self, mock_post, tmp_path, monkeypatch):
        monkeypatch.delenv("IG_TRACKER_DISCORD_WEBHOOK", raising=False)
        config_file = tmp_path / "config.json"
        data_file = tmp_path / "data.json"
        config_file.write_text(json.dumps({"usernames": ["user1"]}))

        collector = InstagramCollectorBase(
            config_file=str(config_file),
            data_file=str(data_file),
            discord_webhook=None,
        )

        collector.send_api_failure_notification("Daily")
        mock_post.assert_not_called()
