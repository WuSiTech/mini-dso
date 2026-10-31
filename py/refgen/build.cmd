@echo off
set PYEXE=python
for /f "delims=" %%i in ('%PYEXE% -c "import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),'zig.exe'))"') do set ZIG=%%i
echo ZIG=%ZIG%
"%ZIG%" cc -target thumb-freestanding-eabi -mcpu=cortex_m3 -Os -nostdlib -ffreestanding -fno-builtin -T link.ld -Wl,--entry=Reset_Handler -o refgen.elf refgen.c
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
echo BUILD OK
