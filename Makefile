N64_PYTHON ?= build/n64-python/bin/python
SD_VOLUME ?= /Volumes/DISK_IMG

.PHONY: n64-sd
n64-sd:
	"$(N64_PYTHON)" tools/n64_sd.py --volume "$(SD_VOLUME)"
