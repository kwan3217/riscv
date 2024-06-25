#!/bin/bash -x

riscof --verbose debug run --config=config32.ini --suite=riscv-arch-test/riscv-test-suite/ --env=riscv-arch-test/riscv-test-suite/env --work-dir=riscof_work32 --no-ref-run --no-dut-run
riscof --verbose debug run --config=config64.ini --suite=riscv-arch-test/riscv-test-suite/ --env=riscv-arch-test/riscv-test-suite/env --work-dir=riscof_work64 --no-ref-run --no-dut-run
