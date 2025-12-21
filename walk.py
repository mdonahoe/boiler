import argparse
import json


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
    if node['type'] == 'function_definition':
        if defines_name(node, name):
            return
    if node['type'] == 'if_statement' and has_name(node, name):
        expression, then_block, else_block = extract_if(node)
        keep_then = True
        keep_else = True
        if has_name(expression, name) or has_name(then_block, name):
            keep_then = False
        if has_name(else_block, name):
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('skipname')
    args = parser.parse_args()
    nodes = json.load(open(args.filename))
    chunks = []
    walk(nodes, chunks, args.skipname)
    text = output_text(chunks)
    print(text)

if __name__ == '__main__':
    main()
