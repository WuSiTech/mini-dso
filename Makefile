####### MCU #######

## STC8A8K64D4 @ 45 MHz, set in STC-ISP, H/W Option "Input IRC frequency"
MCU                 ?= STC8A8K64D4
MCU_IRAM            ?= 256
MCU_XRAM            ?= 8192
# 1 KB EEPROM
MCU_CODE_SIZE       ?= 64512

##### Project #####

PROJECT             ?= minidso
# The path for generated files
BUILD_DIR           = build

# TOOLCHAIN_PREFIX     ?= c:/Program Files/SDCC/bin/
# Toolchain is in search path on my computer
TOOLCHAIN_PREFIX     ?= 

# C source folders
USER_CDIRS          := user
# C source single files
USER_CFILES         :=
USER_INCLUDES       := include


## STC8A8K64S4A12 @ 35 MHz
LIB_FLAGS           :=

include ./rules.mk