#!/bin/bash
exec > /home/bot/boiler/example_repos/fish-shell/before/build_output.log 2>&1
set -x
export PATH="/home/bot/.cargo/bin:/home/bot/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:$PATH"
cd /home/bot/boiler/example_repos/fish-shell/before

echo "=== Checking environment ==="
which rustc
rustc --version
which cargo
cargo --version
which cmake
cmake --version

echo "=== Starting build ==="
make -j1
echo "=== Build exit code: $? ==="
