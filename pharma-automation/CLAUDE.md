## RTK Token Optimization All shell commands MUST be prefixed with `rtk` 
when available. Never use bare commands for the following: ### File 
Operations - `rtk read <file>` — instead of `cat`, `head`, `tail`, or Read 
tool - `rtk read <file> -l aggressive` — for large files where only 
structure matters - `rtk ls <dir>` — instead of `ls`, `ls -la`, or Glob 
tool - `rtk find "<pattern>" <dir>` — instead of `find` - `rtk grep 
"<pattern>" <dir>` — instead of `grep`, `rg`, or Grep tool - `rtk diff 
<file1> <file2>` — instead of `diff` ### Git - `rtk git status` — instead 
of `git status` - `rtk git log -n 10` — instead of `git log` - `rtk git 
diff` — instead of `git diff` - `rtk git add <file>` — instead of `git 
add` - `rtk git commit -m "msg"` — instead of `git commit` - `rtk git 
push` — instead of `git push` - `rtk git pull` — instead of `git pull` ### 
Build & Test - `rtk cargo test` — instead of `cargo test` - `rtk cargo 
build` — instead of `cargo build` - `rtk cargo clippy` — instead of `cargo 
clippy` - `rtk npm test` — instead of `npm test` - `rtk pytest` — instead 
of `pytest` ### Rules - RTK adds <10ms overhead. Never skip it for 
performance reasons. - If unsure whether rtk supports a command, prefix it 
with `rtk` anyway — unknown commands pass through transparently.
- Prefer rtk shell equivalents over Claude's built-in Read, Grep, and Glob tools.

---

# Project Context — pharma-automation

## Scale & Usage
- Single pharmacy (튼튼약국), not multi-tenant
- 3 users maximum (pharmacist + 2 staff)
- ~150 patients/day, ~600 prescriptions/week
- ~544 drugs in master, ~142 cassette mappings
- Agent1 syncs every 5 minutes from one Windows PC
- No public internet exposure — internal pharmacy network + one cloud server

## What this means for code reviews
- Connection pool size 5 is fine. We will never have 15 concurrent requests.
- O(n²) on lists under 1,000 items is not a performance issue. Don't flag it.
- Sequential sync operations (10s total) in a 300s polling cycle are fine.
- PostgreSQL default tuning is adequate for our data volume.
- Code splitting, React.memo, and frontend performance optimizations are premature.
- "What if this scales to 100 pharmacies" is not a relevant question. It won't.
- String comparisons without enum enforcement are fine when we control all writes.
- Client-side timestamps are acceptable — one machine, one timezone.

## What actually matters
- Correctness: drugs must resolve correctly across PM+20's three code systems (internal/insurance/registration)
- Data integrity: narcotics audit trail, optimistic locking, no silent data loss
- Sync reliability: offline queue, graceful restart, no duplicate visits
- Security basics: no hardcoded secrets, field length limits, role enforcement
- Test coverage on critical paths: sync, narcotics, OCR confirm/cancel

## PM+20 Code Systems (critical — source of most bugs)
- DA_Goods.Goods_code (ZD00000001) = PM+20 internal code
- TBSIM040_01.DRUG_CODE (671806320) = insurance code (186K master)
- DA_Goods.Goods_RegNo (DMS0112000006) = registration code
- NO direct mapping between internal and insurance codes
- TEMP_STOCK, TBSID040_04 use insurance codes
- DA_Goods, DA_SUB_PHARM use internal codes

## Tech stack
- Cloud: FastAPI + PostgreSQL (async, SQLAlchemy) + Docker on Mac Mini M4
- Agent1: Python + pymssql on Windows (PM+20 PC)
- Frontend: React 18 TypeScript PWA
- DB migrations: Alembic only, no exceptions

## Review guidelines
- Flag only issues with real user impact (bugs, data loss, security holes)
- Do NOT suggest architectural patterns for scale we don't have
- Do NOT create abstractions preemptively
- Do NOT flag single-pharmacy assumptions as problems
- Performance fixes only when evidence shows actual slowness, not theoretical
- When in doubt: simpler is better
