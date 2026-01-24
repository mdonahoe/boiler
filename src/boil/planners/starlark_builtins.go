// Starlark built-in functions for planner plugins
package planners

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"go.starlark.net/starlark"
)

// MakeBuiltins creates the predeclared built-in functions for Starlark planners.
// gitRef is the default git reference to use for git operations.
func MakeBuiltins(gitRef string) starlark.StringDict {
	return starlark.StringDict{
		"git_show":       starlark.NewBuiltin("git_show", makeGitShowBuiltin(gitRef)),
		"git_grep":       starlark.NewBuiltin("git_grep", makeGitGrepBuiltin(gitRef)),
		"file_exists":    starlark.NewBuiltin("file_exists", fileExistsBuiltin),
		"read_file":      starlark.NewBuiltin("read_file", readFileBuiltin),
		"list_dir":       starlark.NewBuiltin("list_dir", listDirBuiltin),
		"regex_match":    starlark.NewBuiltin("regex_match", regexMatchBuiltin),
		"regex_find_all": starlark.NewBuiltin("regex_find_all", regexFindAllBuiltin),
		"path_join":      starlark.NewBuiltin("path_join", pathJoinBuiltin),
		"path_basename":  starlark.NewBuiltin("path_basename", pathBasenameBuiltin),
		"path_dirname":   starlark.NewBuiltin("path_dirname", pathDirnameBuiltin),
		"path_ext":       starlark.NewBuiltin("path_ext", pathExtBuiltin),
		"log":            starlark.NewBuiltin("log", logBuiltin),
	}
}

// git_show(path, ref="HEAD") -> str or None
// Reads file content from git history at the specified ref.
func makeGitShowBuiltin(defaultRef string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
	return func(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
		var path string
		ref := defaultRef
		if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path, "ref?", &ref); err != nil {
			return nil, err
		}

		cmd := exec.Command("git", "show", fmt.Sprintf("%s:%s", ref, path))
		output, err := cmd.Output()
		if err != nil {
			return starlark.None, nil // File not found in git
		}
		return starlark.String(output), nil
	}
}

// git_grep(pattern, ref="HEAD") -> [(file, line_num, content), ...]
// Searches git history for a pattern and returns matches.
func makeGitGrepBuiltin(defaultRef string) func(*starlark.Thread, *starlark.Builtin, starlark.Tuple, []starlark.Tuple) (starlark.Value, error) {
	return func(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
		var pattern string
		ref := defaultRef
		if err := starlark.UnpackArgs(b.Name(), args, kwargs, "pattern", &pattern, "ref?", &ref); err != nil {
			return nil, err
		}

		cmd := exec.Command("git", "grep", "-n", pattern, ref)
		output, _ := cmd.Output() // Ignore error (no matches = empty)

		var results []starlark.Value
		for _, line := range strings.Split(string(output), "\n") {
			if line == "" {
				continue
			}
			// Format: ref:file:linenum:content
			parts := strings.SplitN(line, ":", 4)
			if len(parts) >= 4 {
				lineNum, _ := strconv.Atoi(parts[2])
				results = append(results, starlark.Tuple{
					starlark.String(parts[1]), // file
					starlark.MakeInt(lineNum), // line_num
					starlark.String(parts[3]), // content
				})
			}
		}
		return starlark.NewList(results), nil
	}
}

// file_exists(path) -> bool
// Checks if a file exists in the working directory.
func fileExistsBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var path string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
		return nil, err
	}
	_, err := os.Stat(path)
	return starlark.Bool(err == nil), nil
}

// read_file(path) -> str or None
// Reads file content from the working directory.
func readFileBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var path string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
		return nil, err
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return starlark.None, nil
	}
	return starlark.String(content), nil
}

// list_dir(path) -> [filename, ...]
// Lists directory contents.
func listDirBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var path string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
		return nil, err
	}

	entries, err := os.ReadDir(path)
	if err != nil {
		return starlark.NewList(nil), nil // Empty list on error
	}

	var results []starlark.Value
	for _, entry := range entries {
		results = append(results, starlark.String(entry.Name()))
	}
	return starlark.NewList(results), nil
}

// regex_match(pattern, text) -> {"full": str, "groups": {name: value}} or None
// Matches a regex pattern against text and returns groups.
func regexMatchBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var pattern, text string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "pattern", &pattern, "text", &text); err != nil {
		return nil, err
	}

	re, err := regexp.Compile(pattern)
	if err != nil {
		return nil, fmt.Errorf("invalid regex: %v", err)
	}

	match := re.FindStringSubmatch(text)
	if match == nil {
		return starlark.None, nil
	}

	// Build groups dict from named captures
	groups := starlark.NewDict(len(re.SubexpNames()))
	for i, name := range re.SubexpNames() {
		if name != "" && i < len(match) {
			groups.SetKey(starlark.String(name), starlark.String(match[i]))
		}
	}

	// Return a dict with full match and groups
	result := starlark.NewDict(2)
	result.SetKey(starlark.String("full"), starlark.String(match[0]))
	result.SetKey(starlark.String("groups"), groups)
	return result, nil
}

// regex_find_all(pattern, text) -> [{"full": str, "groups": {...}}, ...]
// Finds all regex matches in text.
func regexFindAllBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var pattern, text string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "pattern", &pattern, "text", &text); err != nil {
		return nil, err
	}

	re, err := regexp.Compile(pattern)
	if err != nil {
		return nil, fmt.Errorf("invalid regex: %v", err)
	}

	matches := re.FindAllStringSubmatch(text, -1)
	var results []starlark.Value

	for _, match := range matches {
		groups := starlark.NewDict(len(re.SubexpNames()))
		for i, name := range re.SubexpNames() {
			if name != "" && i < len(match) {
				groups.SetKey(starlark.String(name), starlark.String(match[i]))
			}
		}

		result := starlark.NewDict(2)
		result.SetKey(starlark.String("full"), starlark.String(match[0]))
		result.SetKey(starlark.String("groups"), groups)
		results = append(results, result)
	}

	return starlark.NewList(results), nil
}

// path_join(*parts) -> str
// Joins path components.
func pathJoinBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var parts []string
	for i := 0; i < args.Len(); i++ {
		s, ok := starlark.AsString(args.Index(i))
		if !ok {
			return nil, fmt.Errorf("path_join: argument %d is not a string", i)
		}
		parts = append(parts, s)
	}
	return starlark.String(filepath.Join(parts...)), nil
}

// path_basename(path) -> str
// Returns the last element of a path.
func pathBasenameBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var path string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
		return nil, err
	}
	return starlark.String(filepath.Base(path)), nil
}

// path_dirname(path) -> str
// Returns the directory of a path.
func pathDirnameBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var path string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
		return nil, err
	}
	return starlark.String(filepath.Dir(path)), nil
}

// path_ext(path) -> str
// Returns the file extension.
func pathExtBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var path string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "path", &path); err != nil {
		return nil, err
	}
	return starlark.String(filepath.Ext(path)), nil
}

// log(message) -> None
// Prints a debug message (when BOIL_VERBOSE is set).
func logBuiltin(thread *starlark.Thread, b *starlark.Builtin, args starlark.Tuple, kwargs []starlark.Tuple) (starlark.Value, error) {
	var message string
	if err := starlark.UnpackArgs(b.Name(), args, kwargs, "message", &message); err != nil {
		return nil, err
	}

	if isVerbose() {
		fmt.Printf("[Plugin] %s\n", message)
	}
	return starlark.None, nil
}

// isVerbose checks if BOIL_VERBOSE is set
func isVerbose() bool {
	v := strings.ToLower(os.Getenv("BOIL_VERBOSE"))
	return v == "1" || v == "true" || v == "yes"
}
