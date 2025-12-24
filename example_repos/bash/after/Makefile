# Simple Makefile for bash tests using testty
# Tests system bash (/bin/bash) using the testty PTY testing framework

.PHONY: test clean

test: testty.py test_bash.py
	python3 -m unittest test_bash -v

clean:
	rm -rf __pycache__ .pytest_cache
