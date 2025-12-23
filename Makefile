.PHONY: all test test-python test-go check check-python check-go quick install uninstall clean

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib/boiler
GOBIN := boil
VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")

all: print-tree/tree_print $(GOBIN)

print-tree/tree_print:
	$(MAKE) -C print-tree tree_print

$(GOBIN): src/boil/**/*.go
	cd src/boil && go build -ldflags "-X main.Version=$(VERSION)" -o ../../$(GOBIN) .

test: test-python test-go

test-python:
	CHECK_MODE=1 python3 -m unittest discover -s tests -p "test*.py"

test-go:
	go test ./src/boil/...

check: check-python check-go

check-python:
	CHECK_MODE=1 SKIP_SLOW_TESTS=1 python3 -m unittest discover -s tests -p "test*.py"

check-go:
	go test ./src/boil/...

quick:
	SKIP_SLOW_TESTS=1 python3 -m unittest discover -s tests -p "test*.py"

install: all
	@echo "Installing boiler to $(PREFIX)..."
	# Create installation directories
	install -d $(BINDIR)
	install -d $(LIBDIR)
	# Install source files (Python code still needed for src_repair.py, etc.)
	cp -r src $(LIBDIR)/
	# Install tree_print binary
	install -m 755 print-tree/tree_print $(BINDIR)/tree_print
	# Install Go boil binary (drop-in replacement for Python version)
	install -m 755 $(GOBIN) $(BINDIR)/boil
	@echo "Installation complete!"
	@echo "boil (Go) and tree_print are now available in $(BINDIR)"

uninstall:
	@echo "Uninstalling boiler from $(PREFIX)..."
	rm -f $(BINDIR)/boil
	rm -f $(BINDIR)/tree_print
	rm -rf $(LIBDIR)
	@echo "Uninstallation complete!"

clean:
	rm -f $(GOBIN)
	$(MAKE) -C print-tree clean
