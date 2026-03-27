"""약품명 fuzzy matching. 2단계: DB ILIKE 후보 추출 → SequenceMatcher 유사도 점수."""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Drug


@dataclass
class MatchResult:
    drug_id: int | None
    drug_name: str | None
    score: float  # 0~1
    confidence: str  # HIGH | MEDIUM | LOW


# 한글 연속 2글자 이상, 영문 2글자 이상, 숫자+단위
_KW_RE = re.compile(r"[가-힣]{2,}|[a-zA-Z]{2,}|\d+\s*(?:mg|ml|g|mcg|iu|%)", re.IGNORECASE)


def _extract_keywords(name: str) -> list[str]:
    """OCR 품목명에서 검색 키워드 추출.

    '아모시실린캡슐250mg' → ['아모시실린캡슐'] (한글 연속 블록)
    키워드가 없으면 원본 전체를 하나의 키워드로 사용.
    """
    keywords = _KW_RE.findall(name)
    if not keywords and len(name) >= 2:
        keywords = [name]
    return keywords


def _calc_score(ocr_name: str, drug_name: str) -> float:
    """문자열 유사도 점수 (0~1)."""
    return SequenceMatcher(None, ocr_name.lower(), drug_name.lower()).ratio()


def _classify_confidence(score: float) -> str:
    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    return "LOW"


async def match_drug(
    db: AsyncSession,
    ocr_item_name: str,
    pharmacy_id: int | None = None,
) -> MatchResult:
    """OCR 추출 품목명과 drugs 테이블을 fuzzy matching.

    1단계: 키워드 ILIKE로 후보 20개 추출
    2단계: SequenceMatcher로 유사도 점수 계산, 최고 점수 반환
    """
    keywords = _extract_keywords(ocr_item_name)
    if not keywords:
        return MatchResult(drug_id=None, drug_name=None, score=0.0, confidence="LOW")

    # 1단계: DB ILIKE 후보 추출
    # 각 키워드로 검색 + 약품명이 OCR 이름에 포함되는 경우도 검색
    filters = [Drug.name.ilike(f"%{kw}%") for kw in keywords]
    # 역방향 검색: DB의 약품명이 OCR 텍스트에 포함될 수 있으므로
    # OCR 텍스트 자체가 약품명을 포함하는 경우도 매칭
    for kw in keywords:
        if len(kw) > 3:
            # 긴 키워드의 앞 3글자로도 검색
            filters.append(Drug.name.ilike(f"%{kw[:3]}%"))
    result = await db.execute(
        select(Drug).where(or_(*filters)).limit(20)
    )
    candidates = result.scalars().all()

    if not candidates:
        return MatchResult(drug_id=None, drug_name=None, score=0.0, confidence="LOW")

    # 2단계: 유사도 점수 계산
    best_score = 0.0
    best_drug: Drug | None = None
    for drug in candidates:
        score = _calc_score(ocr_item_name, drug.name)
        if score > best_score:
            best_score = score
            best_drug = drug

    if best_drug is None:
        return MatchResult(drug_id=None, drug_name=None, score=0.0, confidence="LOW")

    confidence = _classify_confidence(best_score)

    # LOW confidence → drug_id=None (약사 수동 선택 필요)
    if confidence == "LOW":
        return MatchResult(
            drug_id=None,
            drug_name=best_drug.name,
            score=best_score,
            confidence="LOW",
        )

    return MatchResult(
        drug_id=best_drug.id,
        drug_name=best_drug.name,
        score=best_score,
        confidence=confidence,
    )
