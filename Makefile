.PHONY: test check

test:
	python3 -m unittest discover -s tests -p "test*.py"

check:
	SKIP_SLOW_TESTS=1 python3 -m unittest discover -s tests -p "test*.py"
