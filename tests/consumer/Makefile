# A consumer's Makefile, as small as `make help` allows: a variable entry, a
# plain target, and a list entry that stands for one target per word.
THINGS := alpha beta

.PHONY: help build $(THINGS)

##@ Fixture: make [target] [VARIABLE=value ...]
##@ Variables
## MODE=name: How to build; else the one below
MODE ?= plain

help:
	@awk -v list="$(THINGS)" -f build-tools/make-help.awk Makefile Makefile

##@ Build
## build: Every thing
build: $(THINGS)

## <thing>: One thing: <list>
$(THINGS):
	@echo $@
