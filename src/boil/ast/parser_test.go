package ast

import (
	"strings"
	"testing"
)

func TestGetAnnotationsPython(t *testing.T) {
	source := `import os
from typing import List

class Foo:
    def bar(self):
        pass

def baz():
    pass
`
	annotations, err := GetAnnotations([]byte(source), LangPython)
	if err != nil {
		t.Fatalf("GetAnnotations failed: %v", err)
	}

	// Line 0: import os
	if !hasAnnotation(annotations[0], "import", "os") {
		t.Errorf("Line 0 should have import:os, got %v", annotations[0])
	}

	// Line 1: from typing import List
	if !hasAnnotation(annotations[1], "import", "List") {
		t.Errorf("Line 1 should have import:List, got %v", annotations[1])
	}

	// Line 3-5: class Foo
	if !hasAnnotation(annotations[3], "class", "Foo") {
		t.Errorf("Line 3 should have class:Foo, got %v", annotations[3])
	}

	// Line 4-5: def bar (inside class)
	if !hasAnnotation(annotations[4], "function", "bar") {
		t.Errorf("Line 4 should have function:bar, got %v", annotations[4])
	}

	// Line 7-8: def baz
	if !hasAnnotation(annotations[7], "function", "baz") {
		t.Errorf("Line 7 should have function:baz, got %v", annotations[7])
	}
}

func TestGetAnnotationsC(t *testing.T) {
	source := `#include <stdio.h>
#include "myheader.h"

int main(void) {
    return 0;
}
`
	annotations, err := GetAnnotations([]byte(source), LangC)
	if err != nil {
		t.Fatalf("GetAnnotations failed: %v", err)
	}

	// Line 0: #include <stdio.h>
	if !hasAnnotation(annotations[0], "include", "stdio.h") {
		t.Errorf("Line 0 should have include:stdio.h, got %v", annotations[0])
	}

	// Line 1: #include "myheader.h"
	if !hasAnnotation(annotations[1], "include", "myheader.h") {
		t.Errorf("Line 1 should have include:myheader.h, got %v", annotations[1])
	}

	// Line 3-5: int main(void)
	if !hasAnnotation(annotations[3], "function", "main") {
		t.Errorf("Line 3 should have function:main, got %v", annotations[3])
	}
}

func TestRemoveFunction(t *testing.T) {
	source := `int foo(void) {
    return 1;
}

int bar(void) {
    return 2;
}
`
	result, err := RemoveFunction([]byte(source), "foo", LangC)
	if err != nil {
		t.Fatalf("RemoveFunction failed: %v", err)
	}

	if strings.Contains(result, "foo") {
		t.Errorf("Result should not contain 'foo': %s", result)
	}

	if !strings.Contains(result, "bar") {
		t.Errorf("Result should contain 'bar': %s", result)
	}
}

func hasAnnotation(anns []Annotation, annType, name string) bool {
	for _, ann := range anns {
		if ann.Type == annType && ann.Name == name {
			return true
		}
	}
	return false
}
