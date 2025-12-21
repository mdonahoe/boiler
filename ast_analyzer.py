#!/usr/bin/env python3
"""
AST analyzer that extracts function calls and declarations from source files.
Uses tree_print to get the AST as JSON.
"""
import argparse
import json
import subprocess
import sys


def walk_ast(node, results):
    """
    Recursively walk the AST and collect function calls and declarations.

    Args:
        node: Current AST node (dict with 'type' and optionally 'children')
        results: Dict with 'calls' and 'declarations' lists
    """
    if not isinstance(node, dict):
        return

    node_type = node.get('type', '')

    # Handle function declarations/definitions
    if node_type == 'function_definition':
        # For both C and Python
        # Find the identifier (function name)
        for child in node.get('children', []):
            if isinstance(child, dict):
                if child.get('type') == 'identifier':
                    # Python: direct identifier child
                    func_name = child.get('text', '')
                    if func_name:
                        results['declarations'].append(func_name)
                        break
                elif child.get('type') == 'function_declarator':
                    # C: function_declarator contains the identifier
                    for subchild in child.get('children', []):
                        if isinstance(subchild, dict) and subchild.get('type') == 'identifier':
                            func_name = subchild.get('text', '')
                            if func_name:
                                results['declarations'].append(func_name)
                                break

    # Handle function calls
    elif node_type == 'call_expression':
        # C function calls
        for child in node.get('children', []):
            if isinstance(child, dict) and child.get('type') == 'identifier':
                func_name = child.get('text', '')
                if func_name:
                    results['calls'].append(func_name)
                    break

    elif node_type == 'call':
        # Python function calls
        for child in node.get('children', []):
            if isinstance(child, dict):
                # The function being called could be an identifier or attribute
                if child.get('type') == 'identifier':
                    func_name = child.get('text', '')
                    if func_name:
                        results['calls'].append(func_name)
                        break
                elif child.get('type') == 'attribute':
                    # For method calls like obj.method()
                    # Get the attribute name
                    for attr_child in child.get('children', []):
                        if isinstance(attr_child, dict) and attr_child.get('type') == 'identifier':
                            # Get the last identifier (the method name)
                            func_name = attr_child.get('text', '')
                            if func_name:
                                results['calls'].append(func_name)

    # Recursively process children
    for child in node.get('children', []):
        if isinstance(child, dict):
            walk_ast(child, results)


def main():
    parser = argparse.ArgumentParser(
        description='Extract function calls and declarations from source files using tree_print'
    )
    parser.add_argument('--src-file', required=True, help='Source file to analyze')
    args = parser.parse_args()

    # Run tree_print to get the AST as JSON
    try:
        result = subprocess.run(
            ['tree_print', '--json', args.src_file],
            capture_output=True,
            text=True,
            check=True
        )
        ast_json = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running tree_print: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: tree_print command not found", file=sys.stderr)
        sys.exit(1)

    # Parse the JSON
    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Walk the AST and collect results
    results = {'calls': [], 'declarations': []}
    walk_ast(ast, results)

    # Print declarations first
    for decl in results['declarations']:
        print(f"function_declaration: {decl}")

    # Then print calls
    for call in results['calls']:
        print(f"function_call: {call}")


if __name__ == '__main__':
    main()
