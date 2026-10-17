import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
import check_chatgpt_workers as checker


def test_sequential_waits_until_caller_has_verified_previous_worker():
    sessions = [Mock(worker_id=i) for i in (1, 2, 3)]
    pool = Mock(sessions=sessions)
    with patch.object(checker.time, 'sleep') as sleep:
        iterator = checker._sessions_for_check(pool, sequential=True, stagger_seconds=30)
        assert next(iterator) is sessions[0]
        sessions[0].open.assert_called_once()
        sessions[1].open.assert_not_called()
        sleep.assert_not_called()
        assert next(iterator) is sessions[1]
        sleep.assert_called_once_with(30)
        sessions[2].open.assert_not_called()
        assert next(iterator) is sessions[2]
        assert sleep.call_count == 2
        with pytest.raises(StopIteration):
            next(iterator)
    pool.preflight.assert_not_called()
    for session in sessions:
        session.close.assert_not_called()


def test_sequential_stops_when_a_worker_cannot_open():
    sessions = [Mock(worker_id=i) for i in (1, 2, 3)]
    sessions[1].open.side_effect = RuntimeError('blocked')
    pool = Mock(sessions=sessions)
    with patch.object(checker.time, 'sleep'):
        iterator = checker._sessions_for_check(pool, sequential=True)
        next(iterator)
        with pytest.raises(RuntimeError, match='blocked'):
            next(iterator)
    sessions[2].open.assert_not_called()


def test_default_diagnostic_still_uses_pool_preflight():
    pool = Mock(sessions=[Mock()])
    assert list(checker._sessions_for_check(pool)) == pool.sessions
    pool.preflight.assert_called_once()
