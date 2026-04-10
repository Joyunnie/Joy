"""Tests for DrugResolver — dual-code drug lookup."""
import time

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.tables import Drug
from app.services.drug_resolver import DrugResolver
from tests.conftest import seed_session_factory

pytestmark = pytest.mark.asyncio

SUFFIX = str(int(time.time()))[-6:]


@pytest_asyncio.fixture(autouse=True)
async def cleanup_resolver_drugs():
    """Clean test drugs after each test."""
    yield
    async with seed_session_factory() as db:
        await db.execute(
            Drug.__table__.delete().where(Drug.standard_code.like(f"DR_{SUFFIX}_%"))
        )
        await db.commit()


async def _create_drug(
    standard_code: str,
    name: str,
    insurance_code: str | None = None,
) -> Drug:
    async with seed_session_factory() as db:
        drug = Drug(
            standard_code=standard_code,
            name=name,
            category="PRESCRIPTION",
            insurance_code=insurance_code,
        )
        db.add(drug)
        await db.commit()
        await db.refresh(drug)
        return drug


class TestDrugResolverBuild:
    async def test_build_with_empty_sets(self):
        """Empty code sets → resolver that always returns None."""
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(db, set(), set())
        assert resolver.resolve("anything") is None
        assert resolver.resolve(standard_code="anything") is None
        assert resolver.all_drug_ids == set()

    async def test_build_fetches_by_insurance_code(self):
        drug = await _create_drug(f"DR_{SUFFIX}_INS1", "보험약품", insurance_code="INS001")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(db, {"INS001"}, set())
        found = resolver.resolve(insurance_code="INS001")
        assert found is not None
        assert found.id == drug.id

    async def test_build_fetches_by_standard_code(self):
        drug = await _create_drug(f"DR_{SUFFIX}_STD1", "표준약품")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(db, set(), {f"DR_{SUFFIX}_STD1"})
        found = resolver.resolve(standard_code=f"DR_{SUFFIX}_STD1")
        assert found is not None
        assert found.id == drug.id


class TestDrugResolverResolve:
    async def test_insurance_code_takes_priority(self):
        """When both codes provided, insurance_code wins."""
        drug_ins = await _create_drug(f"DR_{SUFFIX}_PRI1", "보험우선", insurance_code="PRI_INS")
        drug_std = await _create_drug(f"DR_{SUFFIX}_PRI2", "표준약품")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(
                db, {"PRI_INS"}, {f"DR_{SUFFIX}_PRI2"}
            )
        found = resolver.resolve(insurance_code="PRI_INS", standard_code=f"DR_{SUFFIX}_PRI2")
        assert found.id == drug_ins.id

    async def test_fallback_to_standard_when_insurance_not_found(self):
        """Insurance code not in DB → falls back to standard_code."""
        drug = await _create_drug(f"DR_{SUFFIX}_FB1", "폴백약품")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(
                db, {"NONEXISTENT"}, {f"DR_{SUFFIX}_FB1"}
            )
        found = resolver.resolve(insurance_code="NONEXISTENT", standard_code=f"DR_{SUFFIX}_FB1")
        assert found.id == drug.id

    async def test_drug_with_both_codes(self):
        """Drug has both insurance and standard codes — resolvable by either."""
        drug = await _create_drug(f"DR_{SUFFIX}_BOTH", "양코드약품", insurance_code="BOTH_INS")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(
                db, {"BOTH_INS"}, {f"DR_{SUFFIX}_BOTH"}
            )
        by_ins = resolver.resolve(insurance_code="BOTH_INS")
        by_std = resolver.resolve(standard_code=f"DR_{SUFFIX}_BOTH")
        assert by_ins.id == drug.id
        assert by_std.id == drug.id

    async def test_resolve_both_none_returns_none(self):
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(db, set(), set())
        assert resolver.resolve(None, None) is None

    async def test_resolve_nonexistent_codes_returns_none(self):
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(
                db, {"GHOST_INS"}, {"GHOST_STD"}
            )
        assert resolver.resolve(insurance_code="GHOST_INS") is None
        assert resolver.resolve(standard_code="GHOST_STD") is None


class TestDrugResolverAllDrugIds:
    async def test_all_drug_ids_mixed(self):
        """all_drug_ids returns union of both maps."""
        d1 = await _create_drug(f"DR_{SUFFIX}_ID1", "약품1", insurance_code="ID_INS1")
        d2 = await _create_drug(f"DR_{SUFFIX}_ID2", "약품2")
        d3 = await _create_drug(f"DR_{SUFFIX}_ID3", "약품3", insurance_code="ID_INS3")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(
                db, {"ID_INS1", "ID_INS3"}, {f"DR_{SUFFIX}_ID2"}
            )
        ids = resolver.all_drug_ids
        assert d1.id in ids
        assert d2.id in ids
        assert d3.id in ids
        assert len(ids) == 3

    async def test_all_drug_ids_deduplicates(self):
        """Drug in both maps counted once."""
        drug = await _create_drug(f"DR_{SUFFIX}_DUP", "중복약품", insurance_code="DUP_INS")
        async with seed_session_factory() as db:
            resolver = await DrugResolver.build(
                db, {"DUP_INS"}, {f"DR_{SUFFIX}_DUP"}
            )
        assert drug.id in resolver.all_drug_ids
        # Same drug in both maps → still one ID
        assert len([x for x in resolver.all_drug_ids if x == drug.id]) == 1
