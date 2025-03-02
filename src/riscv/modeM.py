"""
Implement the Machine (M) mode. This adds the CSRs and handlers
for this mode only.

Created: 2/26/25
"""
from typing import Mapping

from riscv.hart import Hart, InstructionSet, InstructionHandler


class ModeM(InstructionSet):
    csrs = {
        #  Machine Information Registers (Machine level standard read-only)
        0xF11: ("MRO", "mvendorid", "Vendor ID"),
        0xF12: ("MRO", "marchid", "Architecture ID"),
        0xF13: ("MRO", "mimpid", "Implementation ID"),
        0xF14: ("MRO", "mhartid", "Hardware thread ID"),
        #  Machine Trap Setup
        0x300: ("MRW", "mstatus", "Machine status register"),
        0x301: ("MRW", "misa", "ISA and extensions"),
        0x302: ("MRW", "medeleg", "Machine exception delegation register"),
        0x303: ("MRW", "mideleg", "Machine interrupt delegation register"),
        0x304: ("MRW", "mie", "Machine interrupt-enable register"),
        0x305: ("MRW", "mtvec", "Machine trap-handler base address"),
        0x306: ("MRW", "mcounteren", "Machine counter enable"),
        #  Machine Trap Handling
        0x340: ("MRW", "mscratch", "Scratch register for machine trap handlers"),
        0x341: ("MRW", "mepc", "Machine exception program counter"),
        0x342: ("MRW", "mcause", "Machine trap cause"),
        0x343: ("MRW", "mtval", "Machine bad address or instruction"),
        0x344: ("MRW", "mip", "Machine interrupt pending"),
        #  Machine Configuration
        0x30A: ("MRW", "menvcfg", "Machine environment configuration register"),
        0x747: ("MRW", "mseccfg", "Machine security configuration register"),
        #  Machine Memory Protection
        0x3A0: ("MRW", "pmpcfg0", "Physical memory protection configuration"),
        0x3A2: ("MRW", "pmpcfg2", "Physical memory protection configuration"), } | {
        0x3B0 + x: ("MRW", f"pmpaddr{x}", "Physical memory protection address register") for x in
        range(0, 16)} | {
        #  Machine Counter/Timers
        0xB00: ("MRW", "mcycle", "Machine cycle counter"),
        0xB02: ("MRW", "minstret", "Machine instructions-retired counter")} | {
        0xB00 + x: ("MRW", f"mhpmcounter{x}", "Machine performance-monitoring counter") for x in
        range(3, 32)} | {
        #  Machine Counter Setup
        0x320: ("MRW", "mcountinhibit", "Machine counter-inhibit register"), } | {
        0x320 + x: ("MRW", f"mhpmevent{x}", "Machine performance-monitoring event selector") for x in
        range(3, 32)} | {
        #  Debug/Trace Registers (shared with Debug Mode)
        0x7A0: ("MRW", "tselect", "Debug/Trace trigger register select"),
        0x7A1: ("MRW", "tdata1", "First Debug/Trace trigger data register"),
        0x7A2: ("MRW", "tdata2", "Second Debug/Trace trigger data register"),
        0x7A3: ("MRW", "tdata3", "Third Debug/Trace trigger data register"),
        #  Debug Mode Registers
        0x7B0: ("DRW", "dcsr", "Debug control and status register"),
        0x7B1: ("DRW", "dpc", "Debug PC"),
        0x7B2: ("DRW", "dscratch0", "Debug scratch register 0"),
        0x7B3: ("DRW", "dscratch1", "Debug scratch register 1"),
    }
    # CSRs that are only available in RV32
    csrs32 = {
        0x31A: ("MRW", "mepc", "Upper 32 bits of menvcfg, RV32 only"),
        0x3A1: ("MRW", "pmpcfg1", "Physical memory protection configuration, RV32 only"),
        0x3A3: ("MRW", "pmpcfg3", "Physical memory protection configuration, RV32 only"),
        0x757: ("MRW", "mtval", "Upper 32 bits of mseccfg, RV32 only"),
        0xB80: ("MRW", "mcycleh", "Upper 32 bits of mcycle, RV32I only"),
        0xB82: ("MRW", "minstreth", "Upper 32 bits of minstret, RV32I only")} | {
        0xB80 + x: ("MRW", f"mhpmcounter{x}h", f"Upper 32 bits of mhpmcounter{x}, RV32I only") for x in range(3, 32)
    }

    def add_state(self,hart:Hart):
        hart.csr.add_regs(self.csrs)
        if hart.XLEN==32:
            hart.csr.add_regs(self.csrs32)
        if hart.XLEN==32:
            xlen_enc=1
        elif hart.XLEN==64:
            xlen_enc=2
        elif hart.XLEN==128:
            xlen_enc=3
        hart.csr['misa'] = xlen_enc << 30
    class xRET(InstructionHandler):
        """
        Return to a different privilege level. For now we just
        copy the correct CSR (determined by which privilege level
        we are going to) to the pc
        """

        def __init__(self, name: str, csr:int):
            self.name = name
            self.csr = csr
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            hart.pc=hart.csr[self.csr]
        def disasm(self, p: Mapping[str,int], hart: Hart):
            return f"{self.name:7s}"
        def formula(self, p: Mapping[str,int], hart:Hart):
            name=f"0x{self.csr:03x}"
            if self.csr in hart.csr.csrnames:
                name+=f" ({hart.csr.csrnames[self.csr][1]})"
            return f"pc=CSR[{name}]"
    ins_exec = {
        ' __||___ ___|_ _____ ___ _____ |||__||':xRET("MRET",0x341)
    }
    def get_decode_table(self):
        return self.ins_exec


