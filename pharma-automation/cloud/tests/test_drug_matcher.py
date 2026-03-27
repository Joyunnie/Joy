"""약품 매칭 단위 테스트."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.services.drug_matcher import _calc_score, _extract_keywords, match_drug
from tests.conftest import seed_session_factory, _ensure_seed, app_session_factory


def test_extract_keywords():
    keywords = _extract_keywords("아모시실린캡슐250mg")
    assert "아모시실린캡슐" in keywords or any("아모시실린" in kw for kw in keywords)


def test_exact_score():
    score = _calc_score("타이레놀", "타이레놀")
    assert score == 1.0


def test_high_score():
    score = _calc_score("아모시실린캡슐250mg", "아모시실린캡슐250mg")
    assert score >= 0.7


def test_medium_score():
    score = _calc_score("아모시실린", "아모시실린캡슐250mg정")
    assert 0.4 <= score < 1.0


def test_low_score():
    score = _calc_score("완전다른약품", "아모시실린캡슐250mg")
    assert score < 0.4


@pytest.mark.asyncio
async def test_match_drug_with_db():
    """DB에서 약품 매칭 (아모시실린 → 아모시실린 매칭)."""
    await _ensure_seed()
    async with app_session_factory() as db:
        result = await match_drug(db, "아모시실린캡슐250mg")
        assert result.drug_id is not None
        assert result.drug_name == "아모시실린"
        assert result.score > 0


@pytest.mark.asyncio
async def test_match_drug_no_result():
    """매칭 결과 없는 경우."""
    await _ensure_seed()
    async with app_session_factory() as db:
        result = await match_drug(db, "존재하지않는약품XYZ999")
        assert result.drug_id is None
        assert result.confidence == "LOW"
