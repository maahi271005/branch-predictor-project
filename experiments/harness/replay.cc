// Functional branch-stream replay: drives a ChampSim predictor
// (initialize_branch_predictor / predict_branch / last_branch_result) with the
// branch stream produced by extract.cc and reports misprediction statistics.
//
//   replay <warm_M> <sim_M> <file.br>...
//
// Statistics are counted for the branches between instruction warm_M*1M and
// (warm_M+sim_M)*1M. MPKI and accuracy use ChampSim's definitions:
//   accuracy = (branches - mispredictions) / branches   (all branch types)
//   MPKI     = 1000 * mispredictions / sim instructions
// One output line per trace file; the predictor is re-initialised per trace.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "ooo_cpu.h"

int main(int argc, char** argv)
{
    if (argc < 4) { fprintf(stderr, "usage: %s warm_M sim_M file.br...\n", argv[0]); return 1; }
    long warm = atol(argv[1]), sim = atol(argv[2]);
    const uint64_t MARK = ~0ULL;

    for (int f = 3; f < argc; f++) {
        FILE* in = fopen(argv[f], "rb");
        if (!in) { perror(argv[f]); return 1; }
        O3_CPU cpu;
        cpu.initialize_branch_predictor();

        uint64_t br = 0, miss = 0, cbr = 0, cmiss = 0;
        long millions = 0;
        std::vector<uint64_t> buf(1 << 20);
        size_t n;
        bool done = false;
        while (!done && (n = fread(buf.data(), 8, buf.size(), in)) > 0) {
            for (size_t i = 0; i < n; i++) {
                uint64_t w = buf[i];
                if (w == MARK) {
                    if (++millions >= warm + sim) { done = true; break; }
                    continue;
                }
                uint64_t ip = w & ((1ULL << 56) - 1);
                int type = (w >> 56) & 0xF;
                uint8_t taken = w >> 63;
                uint8_t pred = cpu.predict_branch(ip);
                cpu.last_branch_result(ip, taken);
                if (millions >= warm) {
                    br++;
                    miss += (pred != taken);
                    if (type == 3) { cbr++; cmiss += (pred != taken); }
                }
            }
        }
        fclose(in);
        if (millions < warm + sim) fprintf(stderr, "warning: %s shorter than requested window\n", argv[f]);
        double ninstr = (millions - warm) * 1e6;
        const char* base = strrchr(argv[f], '/');
        printf("%s branches=%llu mispredictions=%llu accuracy=%.4f mpki=%.4f cond_branches=%llu cond_mispredictions=%llu cond_mpki=%.4f\n",
               base ? base + 1 : argv[f], (unsigned long long)br, (unsigned long long)miss, 100.0 * (br - miss) / br,
               1000.0 * miss / ninstr, (unsigned long long)cbr, (unsigned long long)cmiss, 1000.0 * cmiss / ninstr);
        fflush(stdout);
    }
    return 0;
}
