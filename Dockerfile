FROM ocaml/opam2
RUN sudo apt install -y m4
RUN opam update; opam install opam-devel && \
		sudo cp /home/opam/.opam/4.07/lib/opam-devel/* /usr/local/bin
RUN opam switch create operf 4.02.3
RUN sudo apt install -y python tmux vim pkg-config zlib1g-dev autoconf libgmp-dev libpcre3-dev procps && \
		opam pin add -y -k git git://github.com/kayceesrk/ocaml-perf && \
		opam pin add -y -k git git://github.com/kayceesrk/operf-macro#opam2 && \
		opam install yojson re
RUN cd && \
		git clone https://github.com/kayceesrk/ocamlbench-scripts.git && \
		cd ocamlbench-scripts && \
		git checkout dockerfile && \
		eval $(opam env) && \
		sh -c "make opamjson2html.native" && \
		opam repo add benches git+https://github.com/kayceesrk/ocamlbench-repo#multicore -a
