// Verifies the target-free backward-branch inference used for IMLI in
// branch/tagescl.bpred against ground truth taken from the trace.
//
//   verify_imli <trace.champsimtrace.xz> <max_instructions>
//
// Ground truth (what ChampSim itself knows, src/ooo_cpu.cc):
//   branch type from the register-usage decoding, target = ip of the next
//   instruction for taken branches, backward <=> target <= ip.
// Inferred (what the predictor can compute from predict_branch(ip) calls only):
//   backward(B) <=> ip of the next branch <= ip(B), learned per branch in a
//   2^12-bit hashed table; "conditional" <=> branch was ever seen not-taken
//   (2^12-bit hashed table).
// Reports (1) agreement of the per-instance backward inference for taken
// branches and (2) agreement of the resulting IMLI counter with an oracle IMLI
// counter, sampled at every conditional branch.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>

struct input_instr {
    uint64_t ip;
    uint8_t is_branch, branch_taken;
    uint8_t destination_registers[2];
    uint8_t source_registers[4];
    uint64_t destination_memory[2];
    uint64_t source_memory[4];
};

enum { REG_SP = 6, REG_FLAGS = 25, REG_IP = 26 };
enum { NOT_BRANCH, DIRECT_JUMP, INDIRECT, CONDITIONAL, DIRECT_CALL, INDIRECT_CALL, RETURN, OTHER };

static int classify(const input_instr& r, int& is_branch, int& taken)
{
    bool rsp = false, wsp = false, rfl = false, rip = false, wip = false, roth = false;
    for (int i = 0; i < 2; i++) {
        if (r.destination_registers[i] == REG_SP) wsp = true;
        else if (r.destination_registers[i] == REG_IP) wip = true;
    }
    for (int i = 0; i < 4; i++) {
        switch (r.source_registers[i]) {
            case 0: break;
            case REG_SP: rsp = true; break;
            case REG_FLAGS: rfl = true; break;
            case REG_IP: rip = true; break;
            default: roth = true;
        }
    }
    is_branch = r.is_branch; taken = r.branch_taken;
    if (!rsp && !rfl && wip && !roth) { is_branch = 1; taken = 1; return DIRECT_JUMP; }
    if (!rsp && !rfl && wip && roth) { is_branch = 1; taken = 1; return INDIRECT; }
    if (!rsp && rip && !wsp && wip && rfl && !roth) { is_branch = 1; return CONDITIONAL; }
    if (rsp && rip && wsp && wip && !rfl && !roth) { is_branch = 1; taken = 1; return DIRECT_CALL; }
    if (rsp && rip && wsp && wip && !rfl && roth) { is_branch = 1; taken = 1; return INDIRECT_CALL; }
    if (rsp && !rip && wsp && wip) { is_branch = 1; taken = 1; return RETURN; }
    if (wip) { is_branch = 1; return OTHER; }
    return NOT_BRANCH;
}

int main(int argc, char** argv)
{
    if (argc < 3) { fprintf(stderr, "usage: %s trace.xz max_instr [log2_table_bits]\n", argv[0]); return 1; }
    uint64_t max_instr = strtoull(argv[2], nullptr, 10);
    FILE* in = popen((std::string("xz -dc '") + argv[1] + "'").c_str(), "r");
    if (!in) return 1;

    const int LOG = argc > 3 ? atoi(argv[3]) : 12, MASK = (1 << LOG) - 1;
    uint8_t* bwd_tab = (uint8_t*)calloc(1 << LOG, 1);
    uint8_t* cond_tab = (uint8_t*)calloc(1 << LOG, 1);
    std::unordered_map<uint64_t, bool> true_bwd;  // static direction of each conditional branch

    uint32_t imli_oracle = 0, imli_inf = 0;
    const uint32_t IMAX = 1023;

    // pending taken branch awaiting the next-branch inference
    bool have_prev = false, prev_taken = false;
    uint64_t prev_ip = 0;

    // previous instruction (to get the true target = next instruction ip)
    input_instr cur, nxt;
    int cur_valid = 0;
    uint64_t n = 0;

    uint64_t taken_br = 0, bwd_agree = 0, bwd_true = 0;
    uint64_t cond_br = 0, imli_agree = 0, imli_nonzero_oracle = 0, imli_nonzero_agree = 0;
    // value histograms in buckets {0, 1-15, 16-1022, 1023(saturated)}
    uint64_t hist_o[4] = {0, 0, 0, 0}, hist_i[4] = {0, 0, 0, 0}, agree_small = 0;
    auto bucket = [&](uint32_t v) { return v == 0 ? 0 : v < 16 ? 1 : v < IMAX ? 2 : 3; };

    while (n < max_instr && fread(&nxt, sizeof nxt, 1, in) == 1) {
        if (cur_valid) {
            int is_branch, taken;
            int type = classify(cur, is_branch, taken);
            if (is_branch) {
                // ---- inferred mechanism: runs at predict time of this branch
                if (have_prev && prev_taken) {
                    bool b = cur.ip <= prev_ip;
                    bwd_tab[(prev_ip ^ (prev_ip >> LOG)) & MASK] = b;
                    if (b && cond_tab[(prev_ip ^ (prev_ip >> LOG)) & MASK] && imli_inf < IMAX) imli_inf++;
                }
                // ---- compare counters as seen when predicting this branch
                if (type == CONDITIONAL) {
                    cond_br++;
                    imli_agree += (imli_oracle == imli_inf);
                    hist_o[bucket(imli_oracle)]++; hist_i[bucket(imli_inf)]++;
                    agree_small += ((imli_oracle < 16 ? imli_oracle : 16) == (imli_inf < 16 ? imli_inf : 16));
                    if (imli_oracle) { imli_nonzero_oracle++; imli_nonzero_agree += (imli_oracle == imli_inf); }
                }
                // ---- ground truth
                if (taken) {
                    bool tb = nxt.ip <= cur.ip;
                    bool ib = false;  // per-instance inference is evaluated when the next branch arrives;
                    (void)ib;        // here we use the next *instruction*, so store and check below
                    taken_br++;
                    bwd_true += tb;
                    if (type == CONDITIONAL) true_bwd[cur.ip] = tb;
                }
                if (type == CONDITIONAL) {
                    auto it = true_bwd.find(cur.ip);
                    if (it != true_bwd.end() && it->second) {
                        if (taken) { if (imli_oracle < IMAX) imli_oracle++; }
                        else imli_oracle = 0;
                    }
                }
                // ---- inferred mechanism: result callback
                if (!taken) {
                    cond_tab[(cur.ip ^ (cur.ip >> LOG)) & MASK] = 1;
                    if (bwd_tab[(cur.ip ^ (cur.ip >> LOG)) & MASK]) imli_inf = 0;
                }
                prev_ip = cur.ip; prev_taken = taken; have_prev = true;
            }
        }
        cur = nxt; cur_valid = 1; n++;
    }
    pclose(in);

    // second pass statistic: per-instance backward inference needs the next
    // branch, computed in a separate simple loop for clarity
    in = popen((std::string("xz -dc '") + argv[1] + "'").c_str(), "r");
    bool pend = false; uint64_t pend_ip = 0; bool pend_true = false;
    cur_valid = 0; n = 0;
    while (n < max_instr && fread(&nxt, sizeof nxt, 1, in) == 1) {
        if (cur_valid) {
            int is_branch, taken;
            classify(cur, is_branch, taken);
            if (is_branch) {
                if (pend) { bwd_agree += ((cur.ip <= pend_ip) == pend_true); pend = false; }
                if (taken) { pend = true; pend_ip = cur.ip; pend_true = nxt.ip <= cur.ip; }
            }
        }
        cur = nxt; cur_valid = 1; n++;
    }
    pclose(in);

    const char* base = strrchr(argv[1], '/');
    printf("%-40s HIST oracle[0|1-15|16-1022|sat]=%.1f/%.1f/%.1f/%.1f%% inferred=%.1f/%.1f/%.1f/%.1f%% agree(min(v,16))=%.2f%%\n",
           base ? base + 1 : argv[1],
           100.0 * hist_o[0] / cond_br, 100.0 * hist_o[1] / cond_br, 100.0 * hist_o[2] / cond_br, 100.0 * hist_o[3] / cond_br,
           100.0 * hist_i[0] / cond_br, 100.0 * hist_i[1] / cond_br, 100.0 * hist_i[2] / cond_br, 100.0 * hist_i[3] / cond_br,
           100.0 * agree_small / cond_br);
    printf("%-40s taken=%llu backward=%.2f%% inference_agree=%.5f%% | cond=%llu imli_agree=%.4f%% imli_nonzero_agree=%.4f%% (nonzero=%.2f%%)\n",
           base ? base + 1 : argv[1], (unsigned long long)taken_br, 100.0 * bwd_true / taken_br,
           100.0 * bwd_agree / taken_br, (unsigned long long)cond_br, 100.0 * imli_agree / cond_br,
           imli_nonzero_oracle ? 100.0 * imli_nonzero_agree / imli_nonzero_oracle : 100.0,
           100.0 * imli_nonzero_oracle / cond_br);
    return 0;
}
