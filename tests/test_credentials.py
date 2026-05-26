"""Tests for Olympus credential management."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from olympus.credentials import (
    credential_delete,
    credential_get,
    credential_set,
    get_credential,
    set_credential,
)


class TestCredentialSetGet(unittest.TestCase):
    """Test Keychain credential storage."""

    def test_set_and_get_credential(self):
        success = credential_set("test_service", "test_key", "test_value")
        assert success is True

        value = credential_get("test_service", "test_key")
        assert value == "test_value"

        # Cleanup
        credential_delete("test_service", "test_key")

    def test_get_nonexistent_credential(self):
        value = credential_get("nonexistent", "key")
        assert value is None

    def test_delete_credential(self):
        credential_set("test_delete", "key", "value")
        success = credential_delete("test_delete", "key")
        assert success is True

        value = credential_get("test_delete", "key")
        assert value is None


class TestGetCredentialFallback(unittest.TestCase):
    """Test credential fallback chain."""

    def test_keychain_priority(self):
        """Keychain should be checked first."""
        credential_set("fallback_test", "key", "keychain_value")

        with patch.dict(os.environ, {"HERMES_FALLBACK_TEST_KEY": "env_value"}):
            value = get_credential("fallback_test", "key")
            assert value == "keychain_value"

        credential_delete("fallback_test", "key")

    def test_env_fallback(self):
        """Environment variable should be checked if Keychain empty."""
        with patch.dict(os.environ, {"HERMES_TEST_SERVICE_KEY": "env_value"}):
            # Make sure Keychain doesn't have this
            credential_delete("test_service", "key")
            value = get_credential("test_service", "key")
            assert value == "env_value"

    def test_token_file_fallback(self):
        """Token file should be checked if Keychain and env empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hermes_home = Path(tmpdir) / ".hermes"
            service_dir = hermes_home / "test_service"
            service_dir.mkdir(parents=True)

            token_file = service_dir / "token.json"
            token_file.write_text(json.dumps({"key": "token_value"}))

            with patch("olympus.credentials.Path.home", return_value=hermes_home.parent):
                credential_delete("test_service", "key")
                value = get_credential("test_service", "key")
                assert value == "token_value"


class TestSetCredential(unittest.TestCase):
    """Test credential setting."""

    def test_set_credential_stores_in_keychain(self):
        success = set_credential("set_test", "key", "value")
        assert success is True

        value = credential_get("set_test", "key")
        assert value == "value"

        credential_delete("set_test", "key")


if __name__ == "__main__":
    unittest.main()
