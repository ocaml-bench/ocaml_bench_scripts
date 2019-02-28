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

NB: to get the output of the scripts to interleave correctly, you want PYTHONUNBUFFERED=TRUE in the environment
(sadly adding python -u to the shebang doesn't work on Linux)


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

### Interrupts

You want to turn off the interrupt balancing and point everything at core 0. A simple way to acheive this is adding `ENABLED=0` to `/etc/default/irqbalance` on Ubuntu. 
You can also disable the irqbalance service at boot:
```sudo update-rc.d irqbalance disable```

You can check this is working with: 
```watch cat /proc/interrupts```

### nohz_full (tickless mode)

I didn't manage to make this work with a stock Ubuntu kernel. You can check it is working with:
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
  ExecStart=/bin/sh -c "/bin/echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo"
  ExecStop=/bin/sh -c "/bin/echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo"
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

### Interesting links on the subject
 - https://vstinner.github.io/journey-to-stable-benchmark-system.html 
 - https://gist.github.com/Dieterbe/a52c95a9603507670eb39274544ee1a8 (not sure I 100% agree with all in here but gives you some ideas)
 - https://blog.phusion.nl/2017/07/13/understanding-your-benchmarks-and-easy-tips-for-fixing-them/
 - Understanding and isolating the noise in the Linux kernel: https://journals.sagepub.com/doi/abs/10.1177/1094342013477892
