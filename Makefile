.PHONY: install run dev test smoke seed eval audit-verify audit-trace \
        demo-happy demo-failure demo-injection demo-abort demo-tamper cold-start clean

install:
	pip install -r apps/api/requirements.txt

run:
	uvicorn apps.api.main:app --reload --port 8000

dev: run

test:
	pytest -q

smoke:
	@echo "== 13 curl verifications ==" && bash scripts/smoke.sh

seed:
	python -m eval.missions.generate

eval:
	python -m eval.run --missions 100 --reps 3

audit-verify:
	python -m apps.api.audit.verify

audit-trace:
	python -m apps.api.audit.trace

demo-happy:
	bash scripts/demo_happy.sh

demo-failure:
	bash scripts/demo_failure.sh

demo-injection:
	bash scripts/demo_injection.sh

demo-abort:
	bash scripts/demo_abort.sh

demo-tamper:
	bash scripts/demo_tamper.sh

demo-capture:
	curl -X POST http://localhost:8000/demo/capture -H 'Content-Type: application/json' \
	  -d '{"amount_paise":179800,"sku":"BAT-001","mission_id":"MSN-DEMO"}'

cold-start: install smoke
	@echo "== cold-start complete =="

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
