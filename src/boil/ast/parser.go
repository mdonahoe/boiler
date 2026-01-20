// Package ast provides tree-sitter based AST parsing for Python and C code.
// This replaces the external tree_print tool and enables native Go parsing.
package ast

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	sitter "github.com/smacker/go-tree-sitter"
	"github.com/smacker/go-tree-sitter/c"
	"github.com/smacker/go-tree-sitter/python"
)

// Language represents a supported programming language
type Language string

const (
	LangPython Language = "python"
	LangC      Language = "c"
)

// InferLanguage determines the language from a file extension
func InferLanguage(filename string) (Language, error) {
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".py":
		return LangPython, nil
	case ".c", ".h":
		return LangC, nil
	default:
		return "", fmt.Errorf("unknown file extension: %s", ext)
	}
}

// Parser wraps tree-sitter parser functionality
type Parser struct {
	parser *sitter.Parser
	lang   Language
}

// NewParser creates a new parser for the given language
func NewParser(lang Language) (*Parser, error) {
	parser := sitter.NewParser()

	var tsLang *sitter.Language
	switch lang {
	case LangPython:
		tsLang = python.GetLanguage()
	case LangC:
		tsLang = c.GetLanguage()
	default:
		return nil, fmt.Errorf("unsupported language: %s", lang)
	}

	parser.SetLanguage(tsLang)
	return &Parser{parser: parser, lang: lang}, nil
}

// Parse parses source code and returns the root node
func (p *Parser) Parse(source []byte) (*sitter.Node, error) {
	tree, err := p.parser.ParseCtx(context.Background(), nil, source)
	if err != nil {
		return nil, err
	}
	return tree.RootNode(), nil
}

// Annotation represents a label attached to a line of code
type Annotation struct {
	Type string // "function", "class", "import", "alias", "include", "decorator"
	Name string // The identifier name
}

func (a Annotation) String() string {
	return fmt.Sprintf("%s:%s", a.Type, a.Name)
}

// LineAnnotations maps line numbers (0-indexed) to their annotations
type LineAnnotations [][]Annotation

// GetAnnotations parses code and returns annotations for each line
func GetAnnotations(source []byte, lang Language) (LineAnnotations, error) {
	parser, err := NewParser(lang)
	if err != nil {
		return nil, err
	}

	root, err := parser.Parse(source)
	if err != nil {
		return nil, err
	}

	// Count lines
	lineCount := strings.Count(string(source), "\n") + 1
	annotations := make(LineAnnotations, lineCount)
	for i := range annotations {
		annotations[i] = []Annotation{}
	}

	switch lang {
	case LangPython:
		annotatePython(root, source, annotations)
	case LangC:
		annotateC(root, source, annotations)
	}

	return annotations, nil
}

// annotatePython walks Python AST and adds annotations
func annotatePython(node *sitter.Node, source []byte, annotations LineAnnotations) {
	nodeType := node.Type()

	switch nodeType {
	case "import_statement":
		annotatePythonImport(node, source, annotations)

	case "import_from_statement":
		annotatePythonFromImport(node, source, annotations)

	case "class_definition":
		annotatePythonClass(node, source, annotations)

	case "function_definition":
		annotatePythonFunction(node, source, annotations)

	case "decorated_definition":
		annotatePythonDecorated(node, source, annotations)
		return // Don't recurse into children, handled by annotatePythonDecorated
	}

	// Recurse into children
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		annotatePython(child, source, annotations)
	}
}

func annotatePythonImport(node *sitter.Node, source []byte, annotations LineAnnotations) {
	startLine := int(node.StartPoint().Row)
	endLine := int(node.EndPoint().Row)

	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		switch child.Type() {
		case "dotted_name":
			// Simple import: import os
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "identifier" {
					name := subchild.Content(source)
					addAnnotation(annotations, startLine, endLine, "import", name)
				}
			}
		case "aliased_import":
			// Aliased import: import bar as baz
			var importName, aliasName string
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "dotted_name" {
					for k := 0; k < int(subchild.ChildCount()); k++ {
						if subsubchild := subchild.Child(k); subsubchild.Type() == "identifier" {
							importName = subsubchild.Content(source)
						}
					}
				} else if subchild.Type() == "identifier" {
					aliasName = subchild.Content(source)
				}
			}
			if importName != "" {
				addAnnotation(annotations, startLine, endLine, "import", importName)
			}
			if aliasName != "" {
				addAnnotation(annotations, startLine, endLine, "alias", aliasName)
			}
		}
	}
}

func annotatePythonFromImport(node *sitter.Node, source []byte, annotations LineAnnotations) {
	startLine := int(node.StartPoint().Row)
	endLine := int(node.EndPoint().Row)

	seenImportKeyword := false

	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		if child.Type() == "import" {
			seenImportKeyword = true
			continue
		}

		if !seenImportKeyword {
			continue
		}

		switch child.Type() {
		case "dotted_name":
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "identifier" {
					name := subchild.Content(source)
					addAnnotation(annotations, startLine, endLine, "import", name)
				}
			}
		case "aliased_import":
			var importName, aliasName string
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "dotted_name" {
					for k := 0; k < int(subchild.ChildCount()); k++ {
						if subsubchild := subchild.Child(k); subsubchild.Type() == "identifier" {
							importName = subsubchild.Content(source)
						}
					}
				} else if subchild.Type() == "identifier" {
					aliasName = subchild.Content(source)
				}
			}
			if importName != "" {
				addAnnotation(annotations, startLine, endLine, "import", importName)
			}
			if aliasName != "" {
				addAnnotation(annotations, startLine, endLine, "alias", aliasName)
			}
		}
	}
}

func annotatePythonClass(node *sitter.Node, source []byte, annotations LineAnnotations) {
	startLine := int(node.StartPoint().Row)
	endLine := int(node.EndPoint().Row)

	// Find class name
	var className string
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		if child.Type() == "identifier" {
			className = child.Content(source)
			break
		}
	}

	if className != "" {
		addAnnotation(annotations, startLine, endLine, "class", className)
	}

	// Recurse into children for nested definitions
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		annotatePython(child, source, annotations)
	}
}

func annotatePythonFunction(node *sitter.Node, source []byte, annotations LineAnnotations) {
	startLine := int(node.StartPoint().Row)
	endLine := int(node.EndPoint().Row)

	// Find function name
	var funcName string
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		if child.Type() == "identifier" {
			funcName = child.Content(source)
			break
		}
	}

	if funcName != "" {
		addAnnotation(annotations, startLine, endLine, "function", funcName)
	}

	// Recurse into children for nested definitions
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		annotatePython(child, source, annotations)
	}
}

func annotatePythonDecorated(node *sitter.Node, source []byte, annotations LineAnnotations) {
	var decorators []struct {
		name      string
		startLine int
		endLine   int
	}
	var decoratedNode *sitter.Node
	var defName string
	var defType string

	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		switch child.Type() {
		case "decorator":
			decoratorName := extractDecoratorName(child, source)
			if decoratorName != "" {
				decorators = append(decorators, struct {
					name      string
					startLine int
					endLine   int
				}{
					name:      decoratorName,
					startLine: int(child.StartPoint().Row),
					endLine:   int(child.EndPoint().Row),
				})
			}
		case "function_definition":
			decoratedNode = child
			defType = "function"
			for j := 0; j < int(child.ChildCount()); j++ {
				if subchild := child.Child(j); subchild.Type() == "identifier" {
					defName = subchild.Content(source)
					break
				}
			}
		case "class_definition":
			decoratedNode = child
			defType = "class"
			for j := 0; j < int(child.ChildCount()); j++ {
				if subchild := child.Child(j); subchild.Type() == "identifier" {
					defName = subchild.Content(source)
					break
				}
			}
		}
	}

	// Annotate decorator lines with both decorator and function/class
	for _, dec := range decorators {
		if defName != "" {
			addAnnotation(annotations, dec.startLine, dec.endLine, defType, defName)
		}
		addAnnotation(annotations, dec.startLine, dec.endLine, "decorator", dec.name)
	}

	// Walk the decorated definition
	if decoratedNode != nil {
		annotatePython(decoratedNode, source, annotations)
	}
}

func extractDecoratorName(node *sitter.Node, source []byte) string {
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		switch child.Type() {
		case "identifier":
			return child.Content(source)
		case "attribute":
			return extractAttributeParts(child, source)
		case "call":
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "identifier" {
					return subchild.Content(source)
				} else if subchild.Type() == "attribute" {
					return extractAttributeParts(subchild, source)
				}
			}
		}
	}
	return ""
}

func extractAttributeParts(node *sitter.Node, source []byte) string {
	var parts []string
	var walk func(*sitter.Node)
	walk = func(n *sitter.Node) {
		for i := 0; i < int(n.ChildCount()); i++ {
			child := n.Child(i)
			if child.Type() == "identifier" {
				parts = append(parts, child.Content(source))
			} else if child.Type() == "attribute" {
				walk(child)
			}
		}
	}
	walk(node)
	return strings.Join(parts, ".")
}

// annotateC walks C AST and adds annotations
func annotateC(node *sitter.Node, source []byte, annotations LineAnnotations) {
	nodeType := node.Type()

	switch nodeType {
	case "preproc_include":
		annotateCInclude(node, source, annotations)

	case "function_definition":
		annotateCFunction(node, source, annotations)
	}

	// Recurse into children
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		annotateC(child, source, annotations)
	}
}

func annotateCInclude(node *sitter.Node, source []byte, annotations LineAnnotations) {
	startLine := int(node.StartPoint().Row)
	endLine := int(node.EndPoint().Row)

	// Handle end line adjustment (tree-sitter quirk)
	if node.EndPoint().Column == 0 && endLine > 0 {
		endLine--
	}

	var includeName string
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		switch child.Type() {
		case "system_lib_string":
			// Extract name from <stdio.h> format
			text := child.Content(source)
			includeName = strings.Trim(text, "<>")
		case "string_literal":
			// Extract name from "something.h" format
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "string_content" {
					includeName = subchild.Content(source)
				}
			}
		}
	}

	if includeName != "" {
		addAnnotation(annotations, startLine, endLine, "include", includeName)
	}
}

func annotateCFunction(node *sitter.Node, source []byte, annotations LineAnnotations) {
	startLine := int(node.StartPoint().Row)
	endLine := int(node.EndPoint().Row)

	// Handle end line adjustment
	if node.EndPoint().Column == 0 && endLine > 0 {
		endLine--
	}

	var funcName string
	for i := 0; i < int(node.ChildCount()); i++ {
		child := node.Child(i)
		switch child.Type() {
		case "function_declarator":
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "identifier" {
					funcName = subchild.Content(source)
				}
			}
		case "pointer_declarator":
			// Pointer return type
			for j := 0; j < int(child.ChildCount()); j++ {
				subchild := child.Child(j)
				if subchild.Type() == "function_declarator" {
					for k := 0; k < int(subchild.ChildCount()); k++ {
						if subsubchild := subchild.Child(k); subsubchild.Type() == "identifier" {
							funcName = subsubchild.Content(source)
						}
					}
				}
			}
		}
	}

	if funcName != "" {
		addAnnotation(annotations, startLine, endLine, "function", funcName)
	}
}

func addAnnotation(annotations LineAnnotations, startLine, endLine int, annType, name string) {
	for line := startLine; line <= endLine && line < len(annotations); line++ {
		annotations[line] = append(annotations[line], Annotation{Type: annType, Name: name})
	}
}

// GetLabels returns all unique labels found in the code
func GetLabels(source []byte, lang Language) (map[string]bool, error) {
	annotations, err := GetAnnotations(source, lang)
	if err != nil {
		return nil, err
	}

	labels := make(map[string]bool)
	for _, lineAnns := range annotations {
		for _, ann := range lineAnns {
			labels[ann.String()] = true
		}
	}
	return labels, nil
}

// GetFunctionNames returns a list of function names defined in the source code
func GetFunctionNames(source []byte, lang Language) ([]string, error) {
	labels, err := GetLabels(source, lang)
	if err != nil {
		return nil, err
	}

	var functions []string
	seen := make(map[string]bool)
	for label := range labels {
		if strings.HasPrefix(label, "function:") {
			name := strings.TrimPrefix(label, "function:")
			if !seen[name] {
				functions = append(functions, name)
				seen[name] = true
			}
		}
	}
	return functions, nil
}

// GetFunctionNamesFromFile reads a file and returns function names
func GetFunctionNamesFromFile(filename string) ([]string, error) {
	lang, err := InferLanguage(filename)
	if err != nil {
		return nil, err
	}

	source, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}

	return GetFunctionNames(source, lang)
}
