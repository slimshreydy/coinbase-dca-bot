setup-ci:
	pip install -r requirements.txt

setup:
	pip install -r requirements.txt

run:
	modal run main.py

lint:
	black -l 120 .
	pylint .

deploy:
	modal deploy main.py