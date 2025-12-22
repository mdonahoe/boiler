import argparse
import json
import subprocess


def extract_if(node):
    if node['type'] != 'if_statement': raise ValueError(node['type'])

    expression = None
    then_block = None
    else_block = None
    for child in node.get('children'):
        if child['type'] == 'parenthesized_expression':
            expression = child
        if child['type'] == 'compound_statement':
            then_block = child
        if child['type'] == 'else_clause':
            else_block = child
    return expression, then_block, else_block


def defines_name(node, name):
    if node['type'] == 'function_declarator':
        first_child = node['children'][0]
        if first_child['type'] == 'identifier' and first_child['text'] == name:
            return True
    return any(defines_name(child, name) for child in node.get('children', []))
            

def has_name(node, name):
    if node is None:
        return False
    if node['type'] == 'identifier':
        if node['text'] == name:
            return True
    for child in node.get('children', []):
        has = has_name(child, name)
        if has:
            return True
    return False

def walk(node, output, name):
    if 'text' in node and 'children' in node:
        print(node)
        raise RuntimeError('oops')
    if 'skip' in node:
        return
    if 'text' in node:
        output.append(node)
        return
    if node['type'] == 'function_definition' and defines_name(node, name):
        return
    if node['type'] == 'expression_statement' and has_name(node, name):
        return
    if node['type'] == 'declaration' and has_name(node, name):
        return
    if node['type'] == 'if_statement' and has_name(node, name):
        expression, then_block, else_block = extract_if(node)
        keep_then = True
        keep_else = else_block is not None
        if has_name(expression, name) or has_name(then_block, name):
            keep_then = False
        if else_block and has_name(else_block, name):
            keep_else = False
        if keep_else and not keep_then:
            # pull out just the statement
            for child in else_block.get('children', []):
                if child['type'] == 'compound_statement':
                    stmt = child
            for child in stmt.get('children'):
                if child.get('text', 'xxx') in '{}':
                    child['skip'] = True
                    output.append(child)
                else:
                    walk(child, output, name)
                    return

        if keep_then and not keep_else:
            if else_block is not None:
                else_block['skip'] = True

        if not keep_then and not keep_else:
            return

    for child in node.get('children',[]):
        walk(child, output, name)


def output_text(chunks):
    prev_row = 0
    prev_col = 0
    strs = []
    for node in chunks:
        row = node['start']['row']
        col = node['start']['column']
        dy = row - prev_row
        if dy > 0:
            strs.append('\n' * dy)
            prev_col = 0
        dx = col - prev_col
        if dx > 0:
            strs.append(' ' * dx)
        if 'text' in node and not node.get('skip', False):
            strs.append(node['text'])
        prev_row = node['end']['row']
        prev_col = node['end']['column']

    text = ''.join(s for s in strs)
    return text

def remove_function(src_file, function_name, inplace=False, json_file=None):
    """
    Remove a function from a source file.

    Args:
        src_file: Path to the source file
        function_name: Name of the function to remove
        inplace: If True, modify the file in-place
        json_file: Optional path to pre-parsed JSON AST

    Returns:
        The modified source code (if not inplace) or None
    """
    import os

    if json_file:
        output = open(json_file).read()
    else:
        # tree_print is in the repository root, not in src/
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tree_print_path = os.path.join(repo_root, "print-tree", "tree_print")
        output = subprocess.check_output([tree_print_path, '--json', src_file])

    nodes = json.loads(output)
    chunks = []
    walk(nodes, chunks, function_name)
    text = output_text(chunks)

    if inplace and src_file:
        with open(src_file, 'w') as out:
            out.write(text)
        return None
    else:
        return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src-file')
    parser.add_argument('--json-file')
    parser.add_argument('skipname')
    parser.add_argument('--inplace', action='store_true')
    args = parser.parse_args()

    result = remove_function(
        args.src_file,
        args.skipname,
        inplace=args.inplace,
        json_file=args.json_file
    )

    if result is not None:
        print(result)

if __name__ == '__main__':
    main()
