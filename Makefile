.PHONY: install run seed initdb serve-frontend test

install:
	pip install -r requirements.txt

initdb:
	python manage.py initdb

seed:
	python manage.py seed

run:
	python -m backend.app

serve-frontend:
	cd frontend && python3 -m http.server 8000

test:
	pytest -q
