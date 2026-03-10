#!/usr/bin/env bash

# !! Need yq !!
# !! EDIT THIS !!
PROFILE="utils/profile.yml"
CONFIG_NAME="config.yml"

mkdir -p ".pcvs/compiler"
mkdir -p ".pcvs/criterion"
mkdir -p ".pcvs/group"
mkdir -p ".pcvs/machine"
mkdir -p ".pcvs/profile"
mkdir -p ".pcvs/runtime"

yq -y ".compiler"  "${PROFILE}" > ".pcvs/compiler/${CONFIG_NAME}"
yq -y ".criterion" "${PROFILE}" > ".pcvs/criterion/${CONFIG_NAME}"
yq -y ".group"     "${PROFILE}" > ".pcvs/group/${CONFIG_NAME}"
yq -y ".machine"   "${PROFILE}" > ".pcvs/machine/${CONFIG_NAME}"
yq -y ".runtime"   "${PROFILE}" > ".pcvs/runtime/${CONFIG_NAME}"

cat > ".pcvs/profile/${CONFIG_NAME}" << EOF
compiler: ${CONFIG_NAME}
criterion: ${CONFIG_NAME}
group: ${CONFIG_NAME}
machine: ${CONFIG_NAME}
runtime: ${CONFIG_NAME}
EOF
