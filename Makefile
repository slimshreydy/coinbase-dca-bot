setup-ci:
	pip install modal

setup:
	pip install -r requirements.txt

run:
	modal run main.py

deploy:
	modal deploy main.py