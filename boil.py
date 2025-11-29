import argparse
import json
import os
import subprocess
import shutil
import sys
import typing as T

import handlers
from handlers import HANDLERS

from session import ctx, new_session

# Import new pipeline system
from pipeline import run_pipeline, GitState, has_pipeline_handlers
from pipeline.handlers import register_all_handlers

"""
git branch "boiling"
cp .git/index .git/boil.index
GIT_INDEX_FILE=.git/boil.index git add .boil hil/
GIT_INDEX_FILE=.git/boil.index git write-tree
git commit-tree 9cb6a377da0c7931ac1a112db026bbab67a6631e -p HEAD -m 'first boil: unhandled error'
git update-ref refs/heads/boiling becd92e6fb329986a153070791e36a294874605d

Also useful to reset the working directory to a particular tree state, without touching index
git restore --source boiling -- .
"""

BOILING_BRANCH = "boiling"


def get_git_dir() -> str:
    """Get the .git directory path, works from any subdirectory of a git repo."""
    return subprocess.check_output(
        ["git", "rev-parse", "--git-dir"], text=True
    ).strip()


def save_changes(parent: str, message: str, branch_name: T.Optional[str] = None) -> str:
    """
    Commit the current working directory, relative to a parent.
    Also update a branch, if given.

    Returns the created commit hash.
    """
    git_dir = get_git_dir()
    index_file = os.path.join(git_dir, "boil.index")
    shutil.copyfile(os.path.join(git_dir, "index"), index_file)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_file
    if os.path.isdir(".boil"):
        subprocess.check_call(["git", "add", ".boil"], env=env)
    subprocess.check_call(["git", "add", "-u"], env=env)
    tree = subprocess.check_output(["git", "write-tree"], env=env, text=True).strip()
    commit = subprocess.check_output(
        ["git", "commit-tree", tree, "-p", parent, "-m", message], env=env, text=True
    ).strip()
    if branch_name:
        subprocess.check_call(
            ["git", "update-ref", f"refs/heads/{branch_name}", commit]
        )
    return commit


def fix(command: T.List[str], num_iterations: int) -> bool:
    """
    Repeatedly run a command, repairing files until it is fixed.
    """
    # create branches at the current location
    ref = ctx().git_ref
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ref, BOILING_BRANCH],
        capture_output=True,
    )
    ancestor_check = result.returncode
    if ancestor_check == 1:
        print("existing boiling session is stale. Deleting")
        subprocess.call(["git", "branch", "-D", BOILING_BRANCH])
        subprocess.call(["git", "branch", BOILING_BRANCH])
        # Also delete the boil directory
        os.system("rm -rf .boil")
        action = "start"
    elif ancestor_check == 128:
        # branch doesn't exist
        subprocess.call(["git", "branch", BOILING_BRANCH])
        action = "start"
    elif ancestor_check == 0:
        # branch exists and is a ancestor of HEAD. proceed.
        action = "resume"
        pass
    else:
        raise ValueError("f{ancestor_check=}")

    start_commit = BOILING_BRANCH

    # add the current working directory to boil-start
    boil_commit = save_changes(
        parent=start_commit,
        message=f"boil_{action}\n\n{' '.join(command)}",
        branch_name=BOILING_BRANCH,
    )

    # load the iteration number from the .boil dir
    os.makedirs(".boil", exist_ok=True)
    
    # Count only iter files
    n = len([f for f in os.listdir(".boil") if f.startswith("iter")])

    # bootstrap
    stdout, stderr, code = handlers.run_command(command)
    if code == 0:
        # there is nothing to fix.
        return True

    while True:
        n += 1
        print(f"Attempt {n}")

        # Print the output for debugging purposes
        print(stdout)
        print(stderr)
        err = stdout + stderr
        with open(f".boil/iter{n}.exit{code}.txt", "w") as out:
            out.write(err)

        exit = False
        message = ""

        # Try new pipeline system first
        pipeline_result = None
        legacy_handler_used = None
        if has_pipeline_handlers():
            print("[Pipeline] Attempting repair with new pipeline system...")

            # Build git state
            git_state = GitState(
                ref=ref,
                deleted_files=handlers.get_deleted_files(ref=ref),
                git_toplevel=handlers.get_git_toplevel()
            )

            # Run pipeline
            pipeline_result = run_pipeline(stderr, stdout, git_state, debug=True)

            if pipeline_result.success and has_changes():
                message = f"fixed with pipeline (modified {len(pipeline_result.files_modified)} file(s))"
                print(f"[Pipeline] Success: {message}")
            else:
                print("[Pipeline] Pipeline did not produce a fix, falling back to old handlers...")

        # Fall back to old handler system if pipeline didn't fix it
        if not message:
            for handler in handlers.HANDLERS:
                if handler(err) and has_changes():
                    legacy_handler_used = handler.__name__
                    message = f"fixed with {handler}"
                    print(f"[Legacy] Used legacy handler: {legacy_handler_used}")
                    break
            else:
                message = "failed to handle this type of error"
                exit = True

        # Save debug JSON with legacy handler info
        if pipeline_result:
            debug_json_path = f".boil/iter{n}.pipeline.json"
            try:
                debug_data = pipeline_result.to_dict()
                debug_data["legacy_handler_used"] = legacy_handler_used
                with open(debug_json_path, "w") as f:
                    json.dump(debug_data, f, indent=2)
                print(f"[Pipeline] Debug info saved to {debug_json_path}")
            except Exception as e:
                print(f"[Pipeline] Warning: Could not save debug JSON: {e}")

        if not has_changes(verbose=True):
            raise RuntimeError("no change")

        boil_commit = save_changes(
            parent=boil_commit,
            message=f"boil_{n}\n\n{message}",
            branch_name=BOILING_BRANCH,
        )

        if exit:
            raise RuntimeError(message)

        # re-run the main command
        stdout, stderr, code = handlers.run_command(command)

        if code == 0:
            # the fix worked!
            return True

        if num_iterations is not None and n >= num_iterations:
            print(f"Reached iteration limit {n}")
            break
    return False


def has_changes(verbose:bool=False) -> bool:
    """
    Look for changes in the working directory relative to the boiling branch
    """
    git_dir = get_git_dir()
    index_file = os.path.join(git_dir, "boil.index")
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_file

    # Check for modified files
    result = subprocess.run(
        ["git", "diff", "--quiet", BOILING_BRANCH],
        capture_output=True,
        env=env
    )
    modified = result.returncode != 0

    # Check for untracked files
    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        env=env,
    )
    untracked = False
    for line in untracked_result.stdout.splitlines():
        if ".boil" in line:
            continue
        print("new", line)
        untracked = True

    changed = modified or untracked

    # Print detailed diff if verbose
    if changed and verbose:
        print(" --- git diff start ---")
        subprocess.call(["git", "--no-pager", "diff", BOILING_BRANCH], env=env)
        print(" --- git diff end ---")

    return changed

def clear_boiling() -> int:
    """
    Delete the boiling branch and the .boil folder
    Does not otherwise change the working directory
    """
    # Try to delete the branch, but don't fail if it doesn't exist
    result = subprocess.run(["git", "branch", "-D", BOILING_BRANCH], 
                           capture_output=True, text=True)
    if result.returncode != 0:
        if "not found" in result.stderr:
            print(f"Branch '{BOILING_BRANCH}' does not exist, nothing to delete")
        else:
            print(f"Warning: could not delete branch: {result.stderr}")

    # Clean up .boil directory
    if os.path.isdir(".boil"):
        print("Removing .boil directory...")
        shutil.rmtree(".boil")

    return 0

def abort_boiling() -> int:
    """
    Abort the current boiling session and restore the working directory
    to the state before boiling started.
    """
    # Check if boiling branch exists
    check_branch = subprocess.run(
        ["git", "rev-parse", "--verify", BOILING_BRANCH],
        capture_output=True
    )
    if check_branch.returncode != 0:
        print("No active boiling session found.")
        return 1

    # Find the boil_start commit
    try:
        boil_start_commit = subprocess.check_output(
            ["git", "log", "--format=%H", "--grep", "boil_start", f"HEAD..{BOILING_BRANCH}"],
            text=True
        ).strip().split('\n')[0]  # Get the first (most recent) match

        if not boil_start_commit:
            print("Error: Could not find boil_start commit on boiling branch.")
            return 1

        print(f"Found boil_start commit: {boil_start_commit}")

        # Get the parent of boil_start (the original state)
        original_commit = subprocess.check_output(
            ["git", "rev-parse", f"{boil_start_commit}^"],
            text=True
        ).strip()

        print(f"Restoring to original commit: {original_commit}")

        # Reset to the original commit
        subprocess.check_call(["git", "reset", "--hard", original_commit])

        # Then apply the changes to the working directory that existed when user called boil.py
        subprocess.check_call(f"git show {boil_start_commit} | git apply --allow-empty", shell=True)

        # Delete the boiling branch
        subprocess.check_call(["git", "branch", "-D", BOILING_BRANCH])

        print("Successfully aborted boiling session.")
        print("Working directory has been restored to pre-boiling state.")

        # Clean up .boil directory
        if os.path.isdir(".boil"):
            print("Removing .boil directory...")
            shutil.rmtree(".boil")

        return 0

    except subprocess.CalledProcessError as e:
        print(f"Error during abort: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Boil your code.")
    parser.add_argument("-n", type=int, help="number of interations")
    parser.add_argument("--ref", type=str, default="HEAD", help="a working commit")
    parser.add_argument(
        "--abort",
        action="store_true",
        help="abort current boiling session and restore working directory",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="remove the boiling branch and folder but not the working directory state",
    )
    parser.add_argument(
        "--handle-error",
        type=str,
        default=None,
        help="path to pre-existing command output for error analysis",
    )
    parser.add_argument(
        "--test-detectors",
        type=str,
        default=None,
        help="test all detectors on the given error file and show verbose output",
    )

    # Use parse_known_args to separate known and unknown arguments
    args, unknown_args = parser.parse_known_args()

    # Handle abort command
    if args.abort:
        return abort_boiling()

    if args.clear:
        return clear_boiling()

    # Handle test-detectors command
    if args.test_detectors:
        err = open(args.test_detectors).read()
        print(f"Testing detectors with error file: {args.test_detectors}")
        print(f"Error content length: {len(err)}")
        print(f"Error content (first 500 chars):")
        print(err[:500])
        print("\n" + "=" * 80)

        register_all_handlers()
        from pipeline.detectors.registry import get_detector_registry
        registry = get_detector_registry()

        print(f"\nTesting {len(registry.list_detectors())} detectors:")
        for detector in registry._detectors:
            print(f"\n--- {detector.name} ---")
            try:
                clues = detector.detect(err, "")
                print(f"Result: {len(clues)} clue(s) found")
                for i, clue in enumerate(clues):
                    print(f"  Clue {i+1}:")
                    print(f"    Type: {clue.clue_type}")
                    print(f"    Confidence: {clue.confidence}")
                    print(f"    Context: {clue.context}")
                    print(f"    Source: {clue.source_line[:100] if clue.source_line else ''}")
            except Exception as e:
                import traceback
                print(f"Error: {e}")
                traceback.print_exc()
        return 0

    # Store the remaining arguments as a single command string
    # TODO(matt): parse leading --dash-commands and complain because they are probs typos.
    command = unknown_args

    # set the global session
    new_session("foo", args.ref, 0, command)

    # Register pipeline handlers
    print("[Pipeline] Registering pipeline handlers...")
    register_all_handlers()

    # If the user passes the error output explicitly, we can handle it and exit.
    if args.handle_error:
        err = open(args.handle_error).read()
        for i, handler in enumerate(HANDLERS):
            print(handler)
            if handler(err):
                print(f"fixed with {handler}")
                break
        else:
            raise RuntimeError("failed to handle this type of error")
        return 0

    # Otherwise, we iteratively run the command and fix errors, up to n times.
    success = fix(command, num_iterations=args.n)
    if not success:
        print(f"failed to fix: {command}")
        return 1
    else:
        print("success")
        return 0


if __name__ == "__main__":
    sys.exit(main())
