"""
Takes in the output of a find/replace script in the format:

file_path:line_number:new_text_for_this_line

and applies the edits to the appropriate files.
"""

import argparse
import fileinput
import sys
import typing as T


def replace_line(filename: str, line_num: int, text: str) -> None:
    """Replace the given numbered line in the specified file with the new text."""
    print(f"{filename}:{line_num}")
    # Use fileinput to modify the file in-place. Prints below will go into the file
    line_processor = fileinput.input(filename, inplace=True)
    for line in line_processor:
        if line_processor.filelineno() == line_num:
            line = text
        print(line, end="")


def apply_edits(in_file: T.TextIO) -> None:
    for line in in_file.readlines():
        filename, line_num_text, text = line.split(":", 2)
        line_num = int(line_num_text)
        replace_line(filename, line_num, text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", help="input file. If not supplied, use stdin")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as in_file:
            apply_edits(in_file)
    else:
        apply_edits(sys.stdin)


if __name__ == "__main__":
    main()
