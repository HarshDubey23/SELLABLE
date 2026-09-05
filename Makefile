.PHONY: install run check dev truth verify-readme test smoke seed eval audit-verify audit-trace verify demo-capture clean

install:
	pip install -r apps/api/requirements.txt -r apps/api/requirements-dev.txt

# The canonical entry point. Sets up .env and dependencies, boots, health
# checks, then prints where to go.
run:
	python run.py

# Same, but exits with a status code instead of serving. Used by CI and by
# "does this work on a clean checkout" verification.
check:
	python run.py --check --no-browser

dev:
	uvicorn apps.api.main:app --reload --port 8000

# Regenerate docs/generated/truth.json. Every number in the README comes
# from this file; nothing in the README is written by hand.
truth:
	python scripts/generate_truth.py

# Fail if the README claims a number the evidence file does not support.
verify-readme:
	python scripts/verify_readme.py

test:
	pytest -q

# Everything CI runs, in the order CI runs it, so a green run here means a
# green run there. This exists because a README whose test count had
# drifted from docs/generated/truth.json turned CI red on a branch whose
# whole test suite passed locally -- the drift check was a Makefile target
# nothing called. A gate nobody runs before pushing is a gate that only
# ever reports, never prevents.
ci:
	python scripts/doctor.py
	pytest -q
	ruff check apps/api/gateway/
	mypy --strict apps/api/gateway/
	python scripts/verify_readme.py
	python scripts/final_verify.py --strict

smoke:
	@echo "== 8 curl verifications ==" && bash scripts/smoke.sh

seed:
	python -m eval.missions.generate

eval:
	python -m eval.run --missions 100 --reps 3

audit-verify:
	python -m apps.api.audit.verify

audit-trace:
	python -m apps.api.audit.trace

verify: test
	@echo "== verify: running smoke + eval (30x2 quick) =="
	bash scripts/smoke.sh
	python -m eval.run --missions 30 --reps 2 --seed 42
	@echo "== verify complete =="

redteam:
	python scripts/redteam.py

demo-ready:
	@echo "== demo-ready: checking env, DB, missions, server =="
	@test -f .env || (echo "FAIL: .env missing — cp .env.example .env" && exit 1)
	@python -c "import os; assert os.getenv('MISSION_HMAC_KEY') or open('.env').read().find('MISSION_HMAC_KEY')!=-1, 'MISSION_HMAC_KEY missing'"
	@test -f missions/happy_path.json || (echo "FAIL: missions not signed — python scripts/sign_mission.py" && exit 1)
	@python scripts/verify_catalog.py
	@curl -sf http://localhost:$${PORT:-8000}/health | grep -q alive || (echo "FAIL: server not alive — make run" && exit 1)
	@echo "== demo-ready: all checks pass =="

demo-check:
	@echo "== demo-check: critical scenarios runnable =="
	curl -sf http://localhost:$${PORT:-8000}/gateway/proof | grep -q '"llm_imports_detected": 0'
	curl -sf http://localhost:$${PORT:-8000}/policy | grep -q '"rules_count": 12'
	python scripts/redteam.py --base http://localhost:$${PORT:-8000} | grep -q "PASS"
	@echo "== demo-check: ok =="

demo-capture:
	curl -X POST http://localhost:$${PORT:-8000}/demo/capture -H 'Content-Type: application/json' \
	  -H "X-API-Key: $${APP_API_KEY:?APP_API_KEY not set - source .env or export it}" \
	  -d '{"amount_paise":179800,"sku":"BAT-001","mission_id":"MSN-DEMO"}'

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
