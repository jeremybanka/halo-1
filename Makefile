N64_PYTHON ?= build/n64-python/bin/python
BOOTSTRAP_PYTHON ?= python3
N64_ARGS ?=
SD_VOLUME ?= /Volumes/DISK_IMG

.PHONY: n64 n64-sd
n64:
	"$(BOOTSTRAP_PYTHON)" tools/n64.py $(N64_ARGS)

n64-sd:
	"$(N64_PYTHON)" tools/n64_sd.py --volume "$(SD_VOLUME)"
