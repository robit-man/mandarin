PYTHON ?= python3
CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2

.PHONY: all run test integration gui package clean
all: build/mandarin-sandbox build/mandarin-office

build/mandarin-sandbox: native/sandbox.c
	mkdir -p build
	$(CC) $(CFLAGS) -Wno-format-truncation $< -Wl,-z,relro,-z,now -lseccomp -o $@

build/mandarin-office: native/office.c
	mkdir -p build
	$(CC) $(CFLAGS) $< -Wl,-z,relro,-z,now -ldl -o $@

run: all
	$(PYTHON) -m mandarin

test: all
	$(PYTHON) -m unittest discover -s tests -p 'test_core.py' -v

integration: all
	$(PYTHON) -m unittest discover -s tests -p 'test_integration.py' -v

gui: all
	sh scripts/run_gui_checks.sh

package: all
	$(PYTHON) scripts/build_package.py

clean:
	rm -rf build dist
