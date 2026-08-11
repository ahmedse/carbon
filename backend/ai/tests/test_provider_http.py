"""
Tests for ai.providers._http — shared HTTP helpers for AI providers.
"""

from unittest.mock import MagicMock, patch

import requests

from ai.providers._http import get_modules, poll_task, post_task


# ── post_task ──────────────────────────────────────────────────────────


class TestPostTask:
    """Unit tests for post_task()."""

    def test_happy_path(self):
        """Successful POST returns parsed JSON result."""
        mock = MagicMock()
        mock.json.return_value = {"result": {"rows": 42}}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.post", return_value=mock) as p:
            rv = post_task("http://p:9100", "sk-abc", "dq.validate", {"row": {}}, instance_id="carbon")

        p.assert_called_once()
        call_args = p.call_args
        assert call_args[0][0] == "http://p:9100/tasks"
        sent = call_args[1]["json"]
        assert sent["auth"]["instance_id"] == "carbon"
        assert sent["auth"]["api_key"] == "sk-abc"
        assert sent["task"]["type"] == "dq.validate"
        assert rv["result"]["rows"] == 42

    def test_uses_default_instance_id(self):
        mock = MagicMock()
        mock.json.return_value = {"result": "ok"}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.post", return_value=mock) as p:
            post_task("http://p:9100", "sk", "some.task", {})

        sent = p.call_args[1]["json"]
        assert sent["auth"]["instance_id"] == "carbon"  # default

    def test_default_timeout(self):
        mock = MagicMock()
        mock.json.return_value = {}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.post", return_value=mock) as p:
            post_task("http://p:9100", "sk", "t", {})

        assert p.call_args[1]["timeout"] == 30  # default

    def test_custom_timeout(self):
        mock = MagicMock()
        mock.json.return_value = {}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.post", return_value=mock) as p:
            post_task("http://p:9100", "sk", "t", {}, timeout=45)

        assert p.call_args[1]["timeout"] == 45

    def test_connection_error(self):
        """post_task catches ConnectionError and returns structured error."""
        with patch("backend.ai.providers._http.requests.post",
                   side_effect=requests.ConnectionError("no route")):
            rv = post_task("http://p:9100", "sk", "t", {})

        assert rv["status"] == "pulse_unavailable"
        assert rv["error"]["code"] == "unreachable"
        assert "unreachable" in rv["error"]["message"]

    def test_timeout(self):
        """post_task catches Timeout and returns structured error."""
        with patch("backend.ai.providers._http.requests.post",
                   side_effect=requests.Timeout("too slow")):
            rv = post_task("http://p:9100", "sk", "t", {})

        assert rv["status"] == "pulse_unavailable"
        assert rv["error"]["code"] == "timeout"

    def test_request_exception(self):
        """post_task catches RequestException and returns structured error."""
        with patch("backend.ai.providers._http.requests.post",
                   side_effect=requests.RequestException("bad")):
            rv = post_task("http://p:9100", "sk", "t", {})

        assert rv["status"] == "pulse_unavailable"
        assert rv["error"]["code"] == "request_failed"

    def test_unexpected_exception(self):
        """post_task catches any Exception and returns generic error."""
        with patch("backend.ai.providers._http.requests.post",
                   side_effect=ValueError("unexpected")):
            rv = post_task("http://p:9100", "sk", "t", {})

        assert rv["status"] == "pulse_unavailable"
        assert rv["error"]["code"] == "unexpected"


# ── get_modules ────────────────────────────────────────────────────────


class TestGetModules:
    """Unit tests for get_modules()."""

    def test_happy_path(self):
        mock = MagicMock()
        mock.json.return_value = {
            "modules": [{"type": "dq.validate", "name": "DQ Validate"}]
        }
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock) as g:
            rv = get_modules("http://p:9100", instance_id="carbon")

        g.assert_called_once()
        call_args = g.call_args
        assert call_args[0][0] == "http://p:9100/tasks/modules"
        assert call_args[1]["params"] == {"instance_id": "carbon"}
        assert call_args[1]["timeout"] == 10  # get_modules default
        assert len(rv["modules"]) == 1
        assert rv["modules"][0]["type"] == "dq.validate"

    def test_default_instance_id(self):
        mock = MagicMock()
        mock.json.return_value = {"modules": []}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock) as g:
            get_modules("http://p:9100")

        assert g.call_args[1]["params"] == {"instance_id": "carbon"}

    def test_custom_timeout(self):
        mock = MagicMock()
        mock.json.return_value = {"modules": []}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock) as g:
            get_modules("http://p:9100", timeout=15)

        assert g.call_args[1]["timeout"] == 15

    def test_connection_error(self):
        with patch("backend.ai.providers._http.requests.get",
                   side_effect=requests.ConnectionError("refused")):
            rv = get_modules("http://p:9100")

        assert rv["modules"] == []
        assert rv["error"]["code"] == "unreachable"
        assert "refused" in rv["error"]["message"]

    def test_timeout(self):
        with patch("backend.ai.providers._http.requests.get",
                   side_effect=requests.Timeout("timed out")):
            rv = get_modules("http://p:9100")

        assert rv["modules"] == []
        assert rv["error"]["code"] == "timeout"

    def test_request_exception(self):
        with patch("backend.ai.providers._http.requests.get",
                   side_effect=requests.RequestException("fail")):
            rv = get_modules("http://p:9100")

        # get_modules only catches Timeout and ConnectionError explicitly;
        # RequestException falls to the generic except Exception handler.
        assert rv["modules"] == []
        assert rv["error"]["code"] == "unexpected"

    def test_unexpected_exception(self):
        with patch("backend.ai.providers._http.requests.get",
                   side_effect=RuntimeError("oops")):
            rv = get_modules("http://p:9100")

        assert rv["modules"] == []
        assert rv["error"]["code"] == "unexpected"


# ── poll_task ──────────────────────────────────────────────────────────


class TestPollTask:
    """Unit tests for poll_task()."""

    def test_returns_immediately_when_already_completed(self):
        """Status 'completed' on first GET returns immediately."""
        mock = MagicMock()
        mock.json.return_value = {"status": "completed", "result": {"x": 1}}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock) as g:
            rv = poll_task("http://p:9100", "sk", "task-1",
                           poll_interval=0.1, max_wait=10)

        g.assert_called_once()  # only one GET
        assert rv["status"] == "completed"
        assert rv["result"]["x"] == 1

    def test_return_immediately_on_failed(self):
        """Status 'failed' returns immediately with error info."""
        mock = MagicMock()
        mock.json.return_value = {"status": "failed", "error": "bad input"}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock) as g:
            rv = poll_task("http://p:9100", "sk", "task-2",
                           poll_interval=0.1, max_wait=10)

        g.assert_called_once()
        assert rv["status"] == "failed"
        assert rv["error"] == "bad input"

    def test_polling_loop_when_running_then_completed(self):
        """Polls until status becomes 'completed'."""
        running = MagicMock()
        running.json.return_value = {"status": "running"}
        running.status_code = 200
        done = MagicMock()
        done.json.return_value = {"status": "completed", "result": 42}
        done.status_code = 200

        with patch("backend.ai.providers._http.requests.get",
                   side_effect=[running, running, done]) as g:
            rv = poll_task("http://p:9100", "sk", "task-3",
                           poll_interval=0.01, max_wait=10)

        assert g.call_count == 3
        assert rv["status"] == "completed"
        assert rv["result"] == 42

    def test_timeout_if_polling_exceeds_max_wait(self):
        """Returns error dict (does not raise) when max_wait exceeded."""
        mock = MagicMock()
        mock.json.return_value = {"status": "running"}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock):
            rv = poll_task("http://p:9100", "sk", "task-4",
                           poll_interval=0.01, max_wait=0.02)

        assert rv["status"] == "pulse_unavailable"
        assert rv["error"]["code"] == "timeout"
        assert "did not complete" in rv["error"]["message"]

    def test_uses_default_connection_params_when_polling(self):
        """GET for poll includes auth header and timeout."""
        mock = MagicMock()
        mock.json.return_value = {"status": "completed", "result": "ok"}
        mock.status_code = 200

        with patch("backend.ai.providers._http.requests.get", return_value=mock) as g:
            poll_task("http://p:9100", "sk-1", "task-5",
                      poll_interval=0.1, max_wait=10)

        call_args = g.call_args
        assert call_args[0][0] == "http://p:9100/tasks/task-5"
        assert call_args[1]["headers"]["Authorization"] == "Bearer sk-1"
        assert call_args[1]["timeout"] == 10
