"""
Implement the User (U) mode. This adds the CSRs and handlers
for this mode only.

Created: 2/26/25
"""
from riscv.hart import Hart, InstructionSet


class ModeU(InstructionSet):
    csrs = {
        # i_csr priv   name       desc
        #  User Trap Setup
        0x000: ("URW", "ustatus", "User status register"),
        0x004: ("URW", "uie", "User interrupt-enable register"),
        0x005: ("URW", "utvec", "User trap handler base address"),
        #  User Trap Handling
        0x040: ("URW", "uscratch", "Scratch register for user trap handlers"),
        0x041: ("URW", "uepc", "User exception program counter"),
        0x042: ("URW", "ucause", "User trap cause"),
        0x043: ("URW", "utval", "User bad address or instruction"),
        0x044: ("URW", "uip", "User interrupt pending")
    }
    def add_state(self,hart:Hart):
        hart.csr.add_regs(self.csrs)
        hart.csr["time"]=0
    def get_decode_table(self):
        return {}

