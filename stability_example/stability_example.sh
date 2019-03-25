#!/bin/sh

set +x

# an example of stability strangeness

# get a pinned 4.08 branch compiler
HASH=a5ce0c2d0611d164adc7bf694687dc24857321f8
curl -s -L https://github.com/ocaml/ocaml/archive/${HASH}.tar.gz | tar xz 
cd ocaml-${HASH}
./configure --prefix `pwd`/opt
make world
make world.opt
make install
cd ..

# compile two copies of the binary
OCAMLOPT=./ocaml-${HASH}/opt/bin/ocamlopt

BUILDDIR=build
SRC=fold_left_while_test.ml

mkdir -p $BUILDDIR
cp ${SRC} ${BUILDDIR}/r0_${SRC}
last_i=0
for i in {1..7} ; do
	cat ${BUILDDIR}/r${last_i}_${SRC} \
	  | sed 's/(\*\*\*\* global dummy \*\*\*\*)/(\*\*\*\* global dummy \*\*\*\*)\
let r'${i}' = ref false/g' \
	  | sed 's/(\*\*\*\* function pad \*\*\*\*)/(\*\*\*\* function pad \*\*\*\*)\
  r'${i}' := false;/g' \
	  > ${BUILDDIR}/r${i}_${SRC}
	last_i=$i
done


for i in {0..7}; do 
	$OCAMLOPT ${BUILDDIR}/r${i}_${SRC} -o ${BUILDDIR}/r${i}_${SRC%.ml}
done

for i in {0..7}; do
	CMD=${BUILDDIR}/r${i}_${SRC%.ml}
	echo $CMD
	time ./$CMD
done
