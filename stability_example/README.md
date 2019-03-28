# Code layout will affect performance

The performance of a function can be affected by its code layout on modern x86 processors. This effect can be surprisingly large (10-20%) on some benchmarks.

The script `stability_example.sh` pulls a known compiler hash where we change the layout of `fold_left_while_test.ml` by adding variables to a the dummy function `foo`. On our E5-2430L v2 (Ivy-Bridge) machine where we have isolated the CPUs, we see very stable times for each binary but very different run times for each binary between (0.96s and 1.12s). 

Alignment effect are a known problem for compiler developers. There is a LLVM talk given by Zia Ansari https://www.youtube.com/watch?v=IX16gcX4vDQ&feature=youtu.be where he describes several effects including:
 - Decoder alignment
 - DSB Throughput and alignment
 - DSB Thrashing and alignment
 - BPU and alignment

A C++ example is presented here https://dendibakh.github.io/blog/2018/01/18/Code_alignment_issues

A useful tool for getting at perf counters on linux is pmu-tools: https://github.com/andikleen/pmu-tools

Potentially interesting perf stat counters if you want to take this further are:
 - idq_uops_not_delivered_core (which measures when there are no uops to schedule as we are waiting)
 - dsb2mite_switches_count (switching between DSB and old MITE for looking up uops)
 - lsd_cycles_active (did the loop stream detector kick in)
 - and many more!
