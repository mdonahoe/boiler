import subprocess
import sys
import difflib

# Run the python_feature_test.py and capture output
result = subprocess.run(
    ["python3", "python_feature_test.py"],
    capture_output=True,
    text=True
)

# Extract only the printed feature lines (filter out unittest output)
output_lines = []
for line in result.stdout.splitlines():
    # Look for lines that match the pattern: "NN. Feature description..."
    if line and len(line) > 3 and line[0:2].isdigit() and line[2] == '.':
        output_lines.append(line)

# Read expected output from python_feature_test.txt
try:
    with open("python_feature_test.txt", "r") as f:
        expected_lines = [line.rstrip() for line in f.readlines() if line.strip()]
except FileNotFoundError:
    print("ERROR: python_feature_test.txt not found!")
    sys.exit(1)

# Compare the outputs
if output_lines == expected_lines:
    print("SUCCESS: All 50 tests produced expected output!")
    print(f"All {len(output_lines)} feature tests matched.")
    sys.exit(0)
else:
    print("ERROR: Output does not match expected results!")
    print(f"\nExpected {len(expected_lines)} lines, got {len(output_lines)} lines\n")

    # Show detailed diff
    print("Differences:")
    print("-" * 80)

    diff = difflib.unified_diff(
        expected_lines,
        output_lines,
        fromfile="python_feature_test.txt",
        tofile="actual output",
        lineterm=""
    )

    diff_output = list(diff)
    if diff_output:
        for line in diff_output:
            print(line)
    else:
        # If unified_diff shows nothing, do side-by-side comparison
        print("\nLine-by-line comparison:")
        max_lines = max(len(expected_lines), len(output_lines))
        for i in range(max_lines):
            expected = expected_lines[i] if i < len(expected_lines) else "[MISSING]"
            actual = output_lines[i] if i < len(output_lines) else "[MISSING]"

            if expected != actual:
                print(f"\nLine {i+1}:")
                print(f"  Expected: {expected}")
                print(f"  Actual:   {actual}")

    print("-" * 80)
    sys.exit(1)
