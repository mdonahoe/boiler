#!/usr/bin/env python3
"""
Profile the dim test to find bottlenecks
"""
import os
import sys
import subprocess
import shutil
import tempfile
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pipeline.handlers import register_all_handlers

def run_dim_test():
    """Run the dim test and time it"""
    register_all_handlers()

    boiler_dir = os.path.dirname(__file__)
    boil_script = os.path.join(boiler_dir, "boil")
    example_before_dir = os.path.join(boiler_dir, "example_repos", "dim", "before")

    # Create temp directory
    tmpdir = tempfile.mkdtemp(prefix="dim_profile_")
    print(f"Working in: {tmpdir}")

    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                      cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"],
                      cwd=tmpdir, check=True, capture_output=True)

        # Copy files
        for item in os.listdir(example_before_dir):
            if item.startswith('.'):
                continue
            src = os.path.join(example_before_dir, item)
            dst = os.path.join(tmpdir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst)

        # Make scripts executable
        for item in os.listdir(example_before_dir):
            if not item.startswith('.'):
                item_path = os.path.join(tmpdir, item)
                if os.path.isfile(item_path) and os.access(os.path.join(example_before_dir, item), os.X_OK):
                    os.chmod(item_path, 0o755)

        # Commit files
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmpdir, check=True, capture_output=True)

        # Delete all files
        for item in os.listdir(tmpdir):
            if item == '.git':
                continue
            item_path = os.path.join(tmpdir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        # Run boil with timing
        start_time = time.time()
        print(f"\n{'='*60}")
        print("Running boil...")
        print(f"{'='*60}\n")

        env = os.environ.copy()
        env['BOIL_VERBOSE'] = '1'
        result = subprocess.run(
            ["python3", os.path.join(boiler_dir, "boil.py"), "-n", "20", "make", "test"],
            cwd=tmpdir,
            env=env,
            capture_output=False
        )

        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"Total test time: {total_time:.3f}s")
        print(f"Exit code: {result.returncode}")
        print(f"{'='*60}\n")

        # Analyze .boil directory
        boil_dir = os.path.join(tmpdir, ".boil")
        if os.path.exists(boil_dir):
            print(f"\n.boil directory contents:")
            for f in sorted(os.listdir(boil_dir)):
                print(f"  {f}")

            # Analyze pipeline JSON files
            print(f"\nTiming from pipeline JSON files:")
            for f in sorted(os.listdir(boil_dir)):
                if f.endswith('.pipeline.json'):
                    import json
                    with open(os.path.join(boil_dir, f)) as jf:
                        data = json.load(jf)
                        if 'timings' in data:
                            print(f"  {f}:")
                            for k, v in data['timings'].items():
                                print(f"    {k}: {v:.3f}s")

        print(f"\nTemp directory preserved at: {tmpdir}")
        return tmpdir

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return tmpdir

if __name__ == "__main__":
    tmpdir = run_dim_test()
    print(f"\nTo clean up: rm -rf {tmpdir}")
