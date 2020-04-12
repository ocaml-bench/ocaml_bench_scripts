#!/bin/sh

# log to the scratch dir
#TIMESTAMP=`date +'%Y%m%d_%H%M%S'`
TIMESTAMP=`date +'%Y%m%d_%H%M'`
SCRATCHDIR=/local/custom/daily

RUNDIR=${SCRATCHDIR}/${TIMESTAMP}
LOGFILE=${RUNDIR}/logfile_${TIMESTAMP}.log
mkdir -p $RUNDIR

echo "Redirecting stdout/stderr to $LOGFILE"

# setup logfile and redirect our stdout and stderr to this file
touch $LOGFILE
exec 1> $LOGFILE
exec 2>&1

echo "Processing in ${RUNDIR}"

# don't allow unset variables
set -o nounset

# be verbose as we execute
set -x

# needed to get the path to include a dune binary
# NB: a full eval $(opam config env) breaks the sandmark build in a strange way...
eval $(opam config env | grep ^PATH=)

# make sure python log files are in order
PYTHONUNBUFFERED=true

# run custom daily runs
cd /home/ctk21/proj/ctk21_bench_config
./daily_run_custom.sh winter.ocamllabs.io_custom.yml
