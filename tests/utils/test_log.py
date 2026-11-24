import logging
from datetime import UTC, datetime

import pytest

from scripts.utils.log import new_log_file, setup_logging
from scripts.utils.paths import LOG_ROOT_ENV_VAR, resolve_log_root


@pytest.fixture
def restore_logging():
    """setup_logging changes the global root logger; undo it after each test."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        handler.close()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def test_log_file_is_grouped_by_step_and_named_by_utc_time(tmp_path):
    now = datetime(2026, 11, 24, 17, 25, 0, tzinfo=UTC)
    path = new_log_file(tmp_path, "model/DCRNN", now)
    assert path == tmp_path / "model" / "DCRNN" / "20261124T172500Z.log"


@pytest.mark.parametrize("step", ["", "/etc", "data/../../outside"])
def test_step_must_be_a_relative_path_inside_the_log_root(tmp_path, step):
    with pytest.raises(ValueError, match="relative path"):
        new_log_file(tmp_path, step)


def test_log_file_records_debug_while_terminal_shows_info(
    tmp_path, capsys, restore_logging
):
    log_file = tmp_path / "data" / "bronze" / "run.log"
    setup_logging(logging.INFO, log_file)

    logger = logging.getLogger("test.run")
    logger.debug("per-file detail")
    logger.info("source built")

    terminal = capsys.readouterr().err
    saved = log_file.read_text(encoding="utf-8")
    assert "source built" in terminal and "per-file detail" not in terminal
    assert "source built" in saved and "per-file detail" in saved


def test_without_log_file_nothing_is_written(tmp_path, restore_logging):
    setup_logging(logging.INFO)
    logging.getLogger("test.run").info("terminal only")
    assert list(tmp_path.iterdir()) == []


def test_log_root_comes_from_argument_then_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv(LOG_ROOT_ENV_VAR, str(tmp_path / "drive"))
    assert resolve_log_root() == tmp_path / "drive"
    assert resolve_log_root(tmp_path / "explicit") == tmp_path / "explicit"
