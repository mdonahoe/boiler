// remove.go provides function removal functionality
// This is a Go port of src_remove.py
package ast

import (
	"os"
	"sort"
	"strings"

	sitter "github.com/smacker/go-tree-sitter"
)

// byteRange represents a range of bytes to remove
type byteRange struct {
	start, end uint32
}

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

	// Collect byte ranges to remove
	var removeRanges []byteRange
	collectRemovals(root, source, functionName, &removeRanges)

	return outputWithRemovals(source, removeRanges), nil
}

// collectRemovals walks the AST and collects byte ranges to remove
func collectRemovals(node *sitter.Node, source []byte, name string, removeRanges *[]byteRange) {
	nodeType := node.Type()

	// Remove function definitions that define the target name
	if nodeType == "function_definition" && definesName(node, name, source) {
		*removeRanges = append(*removeRanges, byteRange{node.StartByte(), node.EndByte()})
		return
	}

	// Remove expression statements that reference the name
	if nodeType == "expression_statement" && hasName(node, name, source) {
		*removeRanges = append(*removeRanges, byteRange{node.StartByte(), node.EndByte()})
		return
	}

	// Remove declarations that reference the name
	if nodeType == "declaration" && hasName(node, name, source) {
		*removeRanges = append(*removeRanges, byteRange{node.StartByte(), node.EndByte()})
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

		if !keepThen && !keepElse {
			// Remove entire if statement
			*removeRanges = append(*removeRanges, byteRange{node.StartByte(), node.EndByte()})
			return
		}

		if keepElse && !keepThen {
			// Remove the if part up to else, keep else body
			// Remove from start of if to start of else block body
			for i := 0; i < int(elseBlock.ChildCount()); i++ {
				child := elseBlock.Child(i)
				if child.Type() == "compound_statement" {
					// Remove: if (...) {...} else {
					// Keep: body of else
					// Remove: }
					*removeRanges = append(*removeRanges, byteRange{node.StartByte(), child.StartByte() + 1}) // +1 to include opening brace
					*removeRanges = append(*removeRanges, byteRange{child.EndByte() - 1, node.EndByte()})     // closing brace
					return
				}
			}
		}

		if keepThen && !keepElse && elseBlock != nil {
			// Remove just the else clause
			*removeRanges = append(*removeRanges, byteRange{elseBlock.StartByte(), elseBlock.EndByte()})
			// Continue to process the then block
		}
	}

	// Recurse into children
	for i := 0; i < int(node.ChildCount()); i++ {
		collectRemovals(node.Child(i), source, name, removeRanges)
	}
}

// outputWithRemovals outputs the source with specified byte ranges removed
func outputWithRemovals(source []byte, removeRanges []byteRange) string {
	if len(removeRanges) == 0 {
		return string(source)
	}

	// Sort ranges by start position
	sort.Slice(removeRanges, func(i, j int) bool {
		return removeRanges[i].start < removeRanges[j].start
	})

	// Merge overlapping ranges
	merged := []byteRange{removeRanges[0]}
	for i := 1; i < len(removeRanges); i++ {
		last := &merged[len(merged)-1]
		curr := removeRanges[i]
		if curr.start <= last.end {
			if curr.end > last.end {
				last.end = curr.end
			}
		} else {
			merged = append(merged, curr)
		}
	}

	// Output source, skipping removed ranges
	var result strings.Builder
	pos := uint32(0)

	for _, r := range merged {
		if r.start > pos {
			result.Write(source[pos:r.start])
		}
		pos = r.end
	}

	if pos < uint32(len(source)) {
		result.Write(source[pos:])
	}

	return result.String()
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
