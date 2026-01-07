#!/bin/bash
set -ex
export PATH="/home/bot/.cargo/bin:$PATH"
cd /home/bot/boiler/example_repos/fish-shell/before
echo "=== Checking Rust version ==="
rustc --version
cargo --version
echo "=== Checking CMake ==="
cmake --version || echo "CMake not found"
echo "=== Starting build ==="
make -j1 2>&1
