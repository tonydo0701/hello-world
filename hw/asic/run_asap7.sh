#!/usr/bin/env bash
# Synthesize, place and route a 64x64 hardwired k_proj block on ASAP7.
#   asic/run_asap7.sh <P> <clock period ps>     e.g. asic/run_asap7.sh 4 1000
# Results land in build/asic/<variant>/{logs,reports,results}.
set -euo pipefail
P=${1:-4}
PERIOD=${2:-1000}
HW=$(cd "$(dirname "$0")/.." && pwd)
REPO=$(cd "$HW/.." && pwd)
VARIANT=kproj64_p${P}
SRC=$HW/build/asic/src/$VARIANT

python3 "$HW/gen/gen_matvec.py" --name k_proj --n 64 --k 64 --p "$P" --seed 1 --out "$SRC"

docker run --rm -v "$REPO:/work" -w /OpenROAD-flow-scripts/flow openroad/orfs:latest bash -c "
  source ../env.sh >/dev/null
  make DESIGN_CONFIG=/work/hw/asic/asap7/config.mk \
       WORK_HOME=/work/hw/build/asic/work \
       VARIANT=$VARIANT SRC_DIR=/work/hw/build/asic/src/$VARIANT \
       CLOCK_PERIOD_PS=$PERIOD NUM_CORES=4 \
       finish
"
