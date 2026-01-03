"""
Tests for deployment configuration - validates that all paths referenced
in deployment files actually exist in the codebase.

This prevents issues like referencing 'trading_bot.py' when the file
is actually at 'src/trading_bot.py'.
"""
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestDockerfilePaths:
    """Validate Python paths in Dockerfiles."""

    def test_dockerfile_trading_bot_cmd_exists(self):
        """Verify Dockerfile.trading-bot CMD points to existing file."""
        dockerfile = PROJECT_ROOT / "deploy" / "Dockerfile.trading-bot"
        content = dockerfile.read_text(encoding="utf-8")

        # Extract CMD path: CMD ["python", "src/trading_bot.py", ...]
        match = re.search(r'CMD\s*\[\s*"python",\s*"([^"]+)"', content)
        assert match, "Could not find CMD in Dockerfile.trading-bot"

        python_path = match.group(1)
        full_path = PROJECT_ROOT / python_path

        assert full_path.exists(), (
            f"Dockerfile.trading-bot CMD references '{python_path}' "
            f"but file does not exist at {full_path}"
        )

    def test_dockerfile_api_cmd_exists(self):
        """Verify Dockerfile.api CMD points to existing module."""
        dockerfile = PROJECT_ROOT / "deploy" / "Dockerfile.api"
        if not dockerfile.exists():
            pytest.skip("Dockerfile.api does not exist")

        content = dockerfile.read_text(encoding="utf-8")

        # Extract uvicorn module: uvicorn src.api:app
        match = re.search(r'uvicorn\s+(\S+):app', content)
        if match:
            module_path = match.group(1).replace(".", "/") + ".py"
            full_path = PROJECT_ROOT / module_path

            assert full_path.exists(), (
                f"Dockerfile.api references module '{match.group(1)}' "
                f"but file does not exist at {full_path}"
            )


class TestGCESetupPaths:
    """Validate Python paths in GCE setup script."""

    def test_gce_trading_bot_service_path(self):
        """Verify gce_setup.sh trading bot service uses correct path."""
        gce_setup = PROJECT_ROOT / "deploy" / "gce_setup.sh"
        content = gce_setup.read_text(encoding="utf-8")

        # Find: python trading_bot.py or python src/trading_bot.py
        matches = re.findall(r'python\s+([\w/]+trading_bot\.py)', content)
        assert matches, "Could not find trading_bot.py reference in gce_setup.sh"

        for python_path in matches:
            full_path = PROJECT_ROOT / python_path

            assert full_path.exists(), (
                f"gce_setup.sh references '{python_path}' "
                f"but file does not exist at {full_path}"
            )

    def test_gce_discord_bot_service_path(self):
        """Verify gce_setup.sh discord bot service uses correct path."""
        gce_setup = PROJECT_ROOT / "deploy" / "gce_setup.sh"
        content = gce_setup.read_text(encoding="utf-8")

        matches = re.findall(r'python\s+([\w/]+discord_bot\.py)', content)
        if not matches:
            pytest.skip("No discord_bot.py reference in gce_setup.sh")

        for python_path in matches:
            # discord_bot.py might be at root or src/
            full_path = PROJECT_ROOT / python_path
            if not full_path.exists():
                # Try without path prefix
                alt_path = PROJECT_ROOT / "discord_bot.py"
                assert alt_path.exists() or full_path.exists(), (
                    f"gce_setup.sh references '{python_path}' "
                    f"but file does not exist"
                )

    def test_gce_daily_report_path(self):
        """Verify gce_setup.sh daily report uses correct path."""
        gce_setup = PROJECT_ROOT / "deploy" / "gce_setup.sh"
        content = gce_setup.read_text(encoding="utf-8")

        matches = re.findall(r'python\s+([\w/]+daily_report\.py)', content)
        if not matches:
            pytest.skip("No daily_report.py reference in gce_setup.sh")

        for python_path in matches:
            full_path = PROJECT_ROOT / python_path

            assert full_path.exists(), (
                f"gce_setup.sh references '{python_path}' "
                f"but file does not exist at {full_path}"
            )

    def test_gce_weekly_report_path(self):
        """Verify gce_setup.sh weekly report uses correct path."""
        gce_setup = PROJECT_ROOT / "deploy" / "gce_setup.sh"
        content = gce_setup.read_text(encoding="utf-8")

        matches = re.findall(r'python\s+([\w/]+weekly_report\.py)', content)
        if not matches:
            pytest.skip("No weekly_report.py reference in gce_setup.sh")

        for python_path in matches:
            full_path = PROJECT_ROOT / python_path

            assert full_path.exists(), (
                f"gce_setup.sh references '{python_path}' "
                f"but file does not exist at {full_path}"
            )


class TestPathConsistency:
    """Ensure paths are consistent across all deployment files."""

    def test_trading_bot_path_consistency(self):
        """Verify trading_bot.py path is same in Dockerfile and gce_setup.sh."""
        dockerfile = PROJECT_ROOT / "deploy" / "Dockerfile.trading-bot"
        gce_setup = PROJECT_ROOT / "deploy" / "gce_setup.sh"

        # Get Dockerfile path
        dockerfile_content = dockerfile.read_text(encoding="utf-8")
        dockerfile_match = re.search(
            r'CMD\s*\[\s*"python",\s*"([^"]+trading_bot\.py)"', dockerfile_content
        )
        assert dockerfile_match, "Could not find trading_bot.py in Dockerfile"
        dockerfile_path = dockerfile_match.group(1)

        # Get gce_setup.sh path (multiline ExecStart with line continuations)
        gce_content = gce_setup.read_text(encoding="utf-8")
        gce_match = re.search(
            r'python\s+([\w/]+trading_bot\.py)\s+--mode\s+paper', gce_content
        )
        assert gce_match, "Could not find trading_bot.py in gce_setup.sh"
        gce_path = gce_match.group(1)

        assert dockerfile_path == gce_path, (
            f"Path mismatch! Dockerfile uses '{dockerfile_path}' "
            f"but gce_setup.sh uses '{gce_path}'"
        )


class TestRequiredFilesExist:
    """Verify all required deployment files exist."""

    @pytest.mark.parametrize("filename", [
        "deploy/Dockerfile.trading-bot",
        "deploy/gce_setup.sh",
        "deploy/cloudbuild.yaml",
        ".github/workflows/deploy.yml",
        "requirements.txt",
    ])
    def test_required_file_exists(self, filename):
        """Verify required deployment file exists."""
        filepath = PROJECT_ROOT / filename
        assert filepath.exists(), f"Required file missing: {filename}"


class TestEntryPointsExist:
    """Verify all Python entry points exist."""

    @pytest.mark.parametrize("entry_point", [
        "src/trading_bot.py",
        "src/api.py",
    ])
    def test_entry_point_exists(self, entry_point):
        """Verify Python entry point exists."""
        filepath = PROJECT_ROOT / entry_point
        assert filepath.exists(), f"Entry point missing: {entry_point}"

    @pytest.mark.parametrize("entry_point", [
        "src/trading_bot.py",
        "src/api.py",
    ])
    def test_entry_point_is_runnable(self, entry_point):
        """Verify Python entry point has valid syntax."""
        filepath = PROJECT_ROOT / entry_point
        if not filepath.exists():
            pytest.skip(f"{entry_point} does not exist")

        content = filepath.read_text(encoding="utf-8")

        # Check for basic Python syntax by compiling
        try:
            compile(content, filepath, "exec")
        except SyntaxError as e:
            pytest.fail(f"{entry_point} has syntax error: {e}")
