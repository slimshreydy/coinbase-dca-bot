setup-ci:
	pip install -r requirements.txt

setup:
	pip install -r requirements.txt
	cp config.template.json config.json
	modal setup

run:
	modal run main.py

push-policy:
	DCA_POLICY=$$(python -c 'import json, sys; json.dump(json.load(sys.stdin), sys.stdout)' < config.json); \
	modal secret create --force dca-policy DCA_POLICY="$$DCA_POLICY"

lint:
	black -l 120 .
	pylint .

deploy:
	modal deploy main.py
