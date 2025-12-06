.PHONY: all test check

all: print-tree/tree_print

print-tree/tree_print:
	$(MAKE) -C print-tree tree_print

test:
	python3 -m unittest discover -s tests -p "test*.py"

check:
	SKIP_SLOW_TESTS=1 python3 -m unittest discover -s tests -p "test*.py"
