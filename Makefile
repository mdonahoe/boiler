.PHONY: all test check install uninstall

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib/boiler

all: print-tree/tree_print

print-tree/tree_print:
	$(MAKE) -C print-tree tree_print

test:
	python3 -m unittest discover -s tests -p "test*.py"

check:
	CHECK_MODE=1 SKIP_SLOW_TESTS=1 python3 -m unittest discover -s tests -p "test*.py"

quick:
	SKIP_SLOW_TESTS=1 python3 -m unittest discover -s tests -p "test*.py"

install: all
	@echo "Installing boiler to $(PREFIX)..."
	# Create installation directories
	install -d $(BINDIR)
	install -d $(LIBDIR)
	# Install source files
	cp -r src $(LIBDIR)/
	# Install tree_print binary
	install -m 755 print-tree/tree_print $(BINDIR)/tree_print
	# Create and install boil wrapper script
	@echo '#!/usr/bin/env bash' > $(BINDIR)/boil
	@echo 'exec python3 $(LIBDIR)/src/boil.py "$$@"' >> $(BINDIR)/boil
	chmod 755 $(BINDIR)/boil
	@echo "Installation complete!"
	@echo "boil and tree_print are now available in $(BINDIR)"

uninstall:
	@echo "Uninstalling boiler from $(PREFIX)..."
	rm -f $(BINDIR)/boil
	rm -f $(BINDIR)/tree_print
	rm -rf $(LIBDIR)
	@echo "Uninstallation complete!"
