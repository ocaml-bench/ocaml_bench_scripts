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
