// remove.go provides function removal functionality
// This is a Go port of src_remove.py
package ast

import (
	"os"
	"strings"

	sitter "github.com/smacker/go-tree-sitter"
)

// RemoveFunction removes a function from source code
// Returns the modified source code
func RemoveFunction(source []byte, functionName string, lang Language) (string, error) {
	parser, err := NewParser(lang)
	if err != nil {
		return "", err
	}

	root, err := parser.Parse(source)
	if err != nil {
		return "", err
	}

	// Collect text chunks to output, skipping the named function
	var chunks []textChunk
	walkForRemoval(root, source, functionName, &chunks, make(map[*sitter.Node]bool))

	return outputText(chunks, source), nil
}

// RemoveFunctionFromFile removes a function from a file
func RemoveFunctionFromFile(filename, functionName string, inplace bool) (string, error) {
	lang, err := InferLanguage(filename)
	if err != nil {
		return "", err
	}

	source, err := os.ReadFile(filename)
	if err != nil {
		return "", err
	}

	result, err := RemoveFunction(source, functionName, lang)
	if err != nil {
		return "", err
	}

	if inplace {
		return "", os.WriteFile(filename, []byte(result), 0644)
	}

	return result, nil
}

type textChunk struct {
	text     string
	startRow uint32
	startCol uint32
	endRow   uint32
	endCol   uint32
	skip     bool
}

// definesName checks if a node defines the given name
func definesName(node *sitter.Node, name string, source []byte) bool {
	if node.Type() == "function_declarator" {
		if node.ChildCount() > 0 {
			firstChild := node.Child(0)
			if firstChild.Type() == "identifier" && firstChild.Content(source) == name {
				return true
			}
		}
	}

	for i := 0; i < int(node.ChildCount()); i++ {
		if definesName(node.Child(i), name, source) {
			return true
		}
	}

	return false
}

// hasName checks if a node contains an identifier with the given name
func hasName(node *sitter.Node, name string, source []byte) bool {
	if node == nil {
		return false
	}

	if node.Type() == "identifier" && node.Content(source) == name {
		return true
	}

	for i := 0; i < int(node.ChildCount()); i++ {
		if hasName(node.Child(i), name, source) {
			return true
		}
	}

	return false
}

// extractIf extracts components of an if statement
func extractIf(node *sitter.Node) (expression, thenBlock, elseBlock *sitter.Node) {
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		switch child.Type() {
		case "parenthesized_expression":
			expression = child
		case "compound_statement":
			thenBlock = child
		case "else_clause":
			elseBlock = child
		}
	}
	return
}

func walkForRemoval(node *sitter.Node, source []byte, name string, chunks *[]textChunk, skipNodes map[*sitter.Node]bool) {
	if skipNodes[node] {
		return
	}

	// If this is a leaf node (has text but no children), add to output
	if node.ChildCount() == 0 {
		*chunks = append(*chunks, textChunk{
			text:     node.Content(source),
			startRow: node.StartPoint().Row,
			startCol: node.StartPoint().Column,
			endRow:   node.EndPoint().Row,
			endCol:   node.EndPoint().Column,
		})
		return
	}

	nodeType := node.Type()

	// Skip function definitions that define the target name
	if nodeType == "function_definition" && definesName(node, name, source) {
		return
	}

	// Skip expression statements that reference the name
	if nodeType == "expression_statement" && hasName(node, name, source) {
		return
	}

	// Skip declarations that reference the name
	if nodeType == "declaration" && hasName(node, name, source) {
		return
	}

	// Handle if statements specially
	if nodeType == "if_statement" && hasName(node, name, source) {
		expression, thenBlock, elseBlock := extractIf(node)

		keepThen := true
		keepElse := elseBlock != nil

		if hasName(expression, name, source) || hasName(thenBlock, name, source) {
			keepThen = false
		}

		if elseBlock != nil && hasName(elseBlock, name, source) {
			keepElse = false
		}

		if keepElse && !keepThen {
			// Pull out just the else statement body
			for i := 0; i < int(elseBlock.ChildCount()); i++ {
				child := elseBlock.Child(i)
				if child.Type() == "compound_statement" {
					// Skip the braces, output the content
					for j := 0; j < int(child.ChildCount()); j++ {
						subchild := child.Child(j)
						text := subchild.Content(source)
						if text == "{" || text == "}" {
							// Add chunk but mark as skip
							*chunks = append(*chunks, textChunk{
								text:     text,
								startRow: subchild.StartPoint().Row,
								startCol: subchild.StartPoint().Column,
								endRow:   subchild.EndPoint().Row,
								endCol:   subchild.EndPoint().Column,
								skip:     true,
							})
						} else {
							walkForRemoval(subchild, source, name, chunks, skipNodes)
							return
						}
					}
				}
			}
		}

		if keepThen && !keepElse && elseBlock != nil {
			skipNodes[elseBlock] = true
		}

		if !keepThen && !keepElse {
			return
		}
	}

	// Recurse into children
	for i := 0; i < int(node.ChildCount()); i++ {
		walkForRemoval(node.Child(i), source, name, chunks, skipNodes)
	}
}

func outputText(chunks []textChunk, source []byte) string {
	var result strings.Builder
	var prevRow, prevCol uint32

	for _, chunk := range chunks {
		if chunk.skip {
			continue
		}

		// Add newlines
		dy := int(chunk.startRow) - int(prevRow)
		if dy > 0 {
			result.WriteString(strings.Repeat("\n", dy))
			prevCol = 0
		}

		// Add spaces
		dx := int(chunk.startCol) - int(prevCol)
		if dx > 0 {
			result.WriteString(strings.Repeat(" ", dx))
		}

		result.WriteString(chunk.text)
		prevRow = chunk.endRow
		prevCol = chunk.endCol
	}

	return result.String()
}
