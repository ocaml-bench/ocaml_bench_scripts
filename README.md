# ocaml_bench_scripts

Scripts to:
  - build an ocaml compiler from a hash (build_ocaml_hash.py)
  - run an operf micro run with a compiler (run_operf_micro.py)
  - load operf micro output into a codespeed instance (load_operf_data.py)
  - run a backfill of build, operf run and load over a collection of VERSION tags (run_backfill.py)

These scripts currently expect a couple of things in some default locations:
  - an ocaml git tree (to query for tags and hashes) checked out to ocaml:
    ```console
	cd <ocaml_bench_scripts location>
    git clone https://github.com/ocaml/ocaml ocaml
    ```

  - a copy of operf-micro which supports the more_yaml option:
  	```console
	cd <ocaml_bench_scripts location>
	git clone https://github.com/ctk21/operf-micro operf-micro --branch feature/ctk21/yaml_summary
    cd operf-micro
    ./configure --prefix=`pwd`/opt && make && make install
   	```

  - a copy of sandmark:
    ```
    cd <ocaml_bench_scripts location> 
    git clone https://github.com/ocamllabs/sandmark sandmark
    ```

NB: to get the output of the scripts to interleave correctly, you want `PYTHONUNBUFFERED=TRUE` in the environment
(sadly adding python -u to the shebang doesn't work on Linux)

## operf-micro crib sheet

You see something interesting from the data, but how do you rerun just that test and see what's going on. Here is how you would rerun the `fibonnaci` test and plot its data:

```console
   mkdir operf_test_dir
   cd my_opref_test_dir
   operf-micro init --bin-dir <path_to_my_ocaml_compiler_bin_dir> my_operf_test
   operf-micro build
   operf-micro run fibonnaci
   operf-micro results --more --selected fibonnaci my_operf_test
   operf-micro plot fibonnaci my_operf_test
```

Full documentation is <a href="https://www.typerex.org/operf-micro.html">here</a>.


## Notes on hardware and OS settings for Linux benchmarking

### Hyperthreading
Best to switch off in the BIOS. You don't want cross-talk between two processes sharing an L1 or L2 cache.

### Linux CPU isolation

You want to run the OS on a given CPU (say 0) and isolate the remaining cores. This will mean that processes can only run there by being explicitly taskset to those cores.

This is a kernel boot parameter, for example on Ubuntu with a 6-core machine, we would add `isolcpus=1,2,3,4,5` to `/etc/default/grub`. Then run `sudo update-grub`. You can check this is working with:
```
cat /sys/devices/system/cpu/isolated
ps -eo psr,command
```

You can schedule tasks to a given cpu with:
```
taskset --cpu-list 5 shasum /dev/zero
```

While this works properly for programs which spawn a single thread, this fails to work for a program launching multiple threads. This has been documented here [isolcpus_taskset_bug](https://bugzilla.kernel.org/show_bug.cgi?id=116701). As per the Linux kernel devs, `isolcpus` completely removes the cores from the scheduler. Thus the ideal way to work around this is by changing the scheduler for the running process from `SCHED_OTHER` (default) to something else. This can be done via the `chrt` command [chrt_ref](http://man7.org/linux/man-pages/man1/chrt.1.html).

```
sudo taskset --cpu-list 2-16 chrt -r 1 <name-of-executable>
```

Note that, this requires sudo. This ensures that the spawned processes are mapped to available hardware cores in your taskset. One point to be careful here is that if you are spawning more threads than hardware cores available, the performance might not be representative, as the scheduler used here is different from the Linux default.

### Removing RCU callbacks
Read-copy-update is a way to maintain shared data structures which are copied over when modified by one of the owners. In certain cases, this can cause the old copy to be unused and thus can be freed. This freeing process is carried out as part of the interrupt processing routines. Thus, it is possible to inform the kernel to not schedule these routines on the isolated cores. This can be done via the `rcu_nocbs` parameter, similar to `isolcpus`. Kernel command line reference [here](https://www.kernel.org/doc/html/v4.14/admin-guide/kernel-parameters.html). You can read more [here](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux_for_real_time/7/html/tuning_guide/offloading_rcu_callbacks)

Similar to `isolcpus`, we would add `rcu_nocbs=1,2,3,4,5` to `/etc/default/grub` and then run `sudo update-grub` to remove cores 1-5 from having to perform the RCU callback. 

Further, despite cores having offloaded the actual callback, they still have to inform the callback cores to perform the callback. Adding the parameter `rcu_nocb_poll` to the kernel command line, relieves even this from the cores, as the the cores responsible for the callbacks poll for wakeup. 

### Interrupts

You want to turn off the interrupt balancing and point everything at core 0. A simple way to acheive this is adding `ENABLED=0` to `/etc/default/irqbalance` on Ubuntu. On Ubuntu I found that you needed to still have the irqbalance service running for this to work; that is you need the `ENABLED=0` flag in the config and the service to execute seeing that flag.

You can check this is working with:
```watch cat /proc/interrupts```

Alternatively, you can set the command line parameter `irqaffinity=0,1,13,14` to ensure that interrupts are always routed to these cores. This can be checked as well by `cat /proc/interrupts` and you should see the interrupts on the non-affinity cores to be very low.

### nohz_full (tickless mode)

This requires a recompile of the stock kernel. The kernel needs to be compiled with a configuration flag called - `CONF_NO_HZ_FULL` and then the command line param `nohz_full` can be added to `/etc/default/grub`.

You can check if this worked at - 
```cat /sys/devices/system/cpu/nohz_full```

### Setting default pstate to performance

You want the CPU to be in default pstate `performance` rather than `powersave`. You can acheive this on Ubuntu with
```
 sudo apt-get install cpufrequtils
 echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils
 sudo systemctl disable ondemand
```

Check that it is working with:
```
sudo tlp stat -p
```

### Turn off turbo-boost

Turbo-boost is not intended to be a sustainable clock speed for an Intel processor. To get a stable clock speed over a prolonged period, you need to switch turbo-boost off. On Ubuntu you can add a `disable-turbo-boost` service with:
```
  cat << EOF | sudo tee \
  /etc/systemd/system/disable-turbo-boost.service
  [Unit]
  Description=Disable Turbo Boost on Intel CPU

  [Service]
  ExecStart=/bin/sh -c "(/bin/echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo) || (/bin/echo 0 > /sys/devices/system/cpu/cpufreq/boost)"
  ExecStop=/bin/sh -c "(/bin/echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo) || (/bin/echo 1 > /sys/devices/system/cpu/cpufreq/boost)"
  RemainAfterExit=yes

  [Install]
  WantedBy=sysinit.target
  EOF
```
Setup the service with
```
sudo systemctl daemon-reload
sudo systemctl start disable-turbo-boost
sudo systemctl enable disable-turbo-boost
```

You can check it is working with
```
sudo tlp stat -p
watch cat /sys/devices/system/cpu/cpu?/cpufreq/scaling_cur_freq
```

Alternatively, Certain BIOS'es will also allow you to turn of TurboBoost.

### ASLR on process runs

Usually processes on linux will have address space layout randomization (ASLR) switched on. You can check if this is the case with
```
cat /proc/sys/kernel/randomize_va_space
```
0 is off, 1 is on, 2 includes the data segments.

You can run a process (and it's children) with ASLR switched off using:
```
setarch `uname -m` --addr-no-randomize <cmd>
```

If you leave ASLR switched on, then for some benchmarks it is possible that you will introduce noise (the operf-micro format benchmarks are a good example). It's important to realize that for a given operf run, the address space layout is the same. Hence all the samples collected are for that specific layout.

If you are doing continuous integration style benchmarking with ASLR on, then you really should run a collection of independent processes to sample over the different layouts. Or be aware that the same binary can give you different results between process runs depending on the layout.

### Interesting links on the subject
 - https://vstinner.github.io/journey-to-stable-benchmark-system.html
 - https://gist.github.com/Dieterbe/a52c95a9603507670eb39274544ee1a8 (not sure I 100% agree with all in here but gives you some ideas)
 - https://blog.phusion.nl/2017/07/13/understanding-your-benchmarks-and-easy-tips-for-fixing-them/
 - Understanding and isolating the noise in the Linux kernel: https://journals.sagepub.com/doi/abs/10.1177/1094342013477892
 - ASLR info: https://linux-audit.com/linux-aslr-and-kernelrandomize_va_space-setting/
 - isolcpus interaction with taskset - https://bugzilla.kernel.org/show_bug.cgi?id=116701
 - Offloading RCU callbacks - https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux_for_real_time/7/html/tuning_guide/offloading_rcu_callbacks

### References
  - Kernel command line reference - https://www.kernel.org/doc/html/v4.14/admin-guide/kernel-parameters.html
