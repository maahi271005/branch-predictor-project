// Minimal stand-in for ChampSim's inc/ooo_cpu.h so that unmodified
// branch/*.bpred files can be compiled into the functional replay harness.
// Only the branch-predictor interface of O3_CPU is provided.
#ifndef OOO_CPU_H
#define OOO_CPU_H

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <vector>

using namespace std;

#define NUM_CPUS 1

class O3_CPU {
  public:
    uint32_t cpu = 0;

    uint8_t predict_branch(uint64_t ip);
    void initialize_branch_predictor(),
         last_branch_result(uint64_t ip, uint8_t taken);
};

#endif
