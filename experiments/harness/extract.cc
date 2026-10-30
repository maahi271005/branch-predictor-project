// Extract the branch stream of a ChampSim (DPC-3) trace into a compact file.
//
//   extract <trace.champsimtrace.xz> <out.br> <max_instructions> [skip_instructions]
//
//   skip_instructions: instructions discarded first (used to build a separate
//   tuning region so that parameters are not tuned on the reported window)
//
// Branch identification and the taken flag follow O3_CPU::read_from_trace()
// in src/ooo_cpu.cc exactly (non-cloudsuite path), so the predictor sees the
// same (ip, taken) sequence of predict_branch()/last_branch_result() calls as
// in ChampSim (old ChampSim has no wrong-path fetch).
//
// Output: a sequence of little-endian uint64 words.
//   branch : ip (bits 0..55) | branch_type (bits 56..59) | taken (bit 63)
//   marker : 0xFFFFFFFFFFFFFFFF, written after every 1,000,000 instructions
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

struct input_instr {  // identical layout to inc/instruction.h
    uint64_t ip;
    uint8_t is_branch, branch_taken;
    uint8_t destination_registers[2];
    uint8_t source_registers[4];
    uint64_t destination_memory[2];
    uint64_t source_memory[4];
};
static_assert(sizeof(input_instr) == 64, "trace record must be 64 bytes");

enum { REG_STACK_POINTER = 6, REG_FLAGS = 25, REG_INSTRUCTION_POINTER = 26 };
enum { NOT_BRANCH, DIRECT_JUMP, INDIRECT, CONDITIONAL, DIRECT_CALL, INDIRECT_CALL, RETURN, OTHER };

int main(int argc, char** argv)
{
    if (argc < 4) { fprintf(stderr, "usage: %s trace.xz out.br max_instr [skip_instr]\n", argv[0]); return 1; }
    uint64_t max_instr = strtoull(argv[3], nullptr, 10);
    uint64_t skip = argc > 4 ? strtoull(argv[4], nullptr, 10) : 0;
    std::string cmd = std::string("xz -dc '") + argv[1] + "'";
    FILE* in = popen(cmd.c_str(), "r");
    FILE* out = fopen(argv[2], "wb");
    if (!in || !out) { perror("open"); return 1; }
    setvbuf(out, nullptr, _IOFBF, 1 << 22);

    input_instr r;
    for (uint64_t k = 0; k < skip; k++)
        if (fread(&r, sizeof r, 1, in) != 1) { fprintf(stderr, "trace shorter than skip\n"); return 2; }

    const uint64_t MARK = ~0ULL;
    uint64_t n = 0, nb = 0;
    while (n < max_instr && fread(&r, sizeof r, 1, in) == 1) {
        bool reads_sp = false, writes_sp = false, reads_flags = false, reads_ip = false, writes_ip = false, reads_other = false;
        for (int i = 0; i < 2; i++) {
            if (r.destination_registers[i] == REG_STACK_POINTER) writes_sp = true;
            else if (r.destination_registers[i] == REG_INSTRUCTION_POINTER) writes_ip = true;
        }
        for (int i = 0; i < 4; i++) {
            switch (r.source_registers[i]) {
                case 0: break;
                case REG_STACK_POINTER: reads_sp = true; break;
                case REG_FLAGS: reads_flags = true; break;
                case REG_INSTRUCTION_POINTER: reads_ip = true; break;
                default: reads_other = true; break;
            }
        }
        int is_branch = r.is_branch, taken = r.branch_taken, type = NOT_BRANCH;
        if (!reads_sp && !reads_flags && writes_ip && !reads_other) { is_branch = 1; taken = 1; type = DIRECT_JUMP; }
        else if (!reads_sp && !reads_flags && writes_ip && reads_other) { is_branch = 1; taken = 1; type = INDIRECT; }
        else if (!reads_sp && reads_ip && !writes_sp && writes_ip && reads_flags && !reads_other) { is_branch = 1; type = CONDITIONAL; }
        else if (reads_sp && reads_ip && writes_sp && writes_ip && !reads_flags && !reads_other) { is_branch = 1; taken = 1; type = DIRECT_CALL; }
        else if (reads_sp && reads_ip && writes_sp && writes_ip && !reads_flags && reads_other) { is_branch = 1; taken = 1; type = INDIRECT_CALL; }
        else if (reads_sp && !reads_ip && writes_sp && writes_ip) { is_branch = 1; taken = 1; type = RETURN; }
        else if (writes_ip) { is_branch = 1; type = OTHER; }

        if (is_branch) {
            uint64_t w = (r.ip & ((1ULL << 56) - 1)) | ((uint64_t)type << 56) | ((uint64_t)(taken != 0) << 63);
            fwrite(&w, 8, 1, out);
            nb++;
        }
        if (++n % 1000000 == 0) fwrite(&MARK, 8, 1, out);
    }
    pclose(in);
    fclose(out);
    fprintf(stderr, "%s: %llu instructions, %llu branches\n", argv[1], (unsigned long long)n, (unsigned long long)nb);
    return n == max_instr ? 0 : 2;
}
