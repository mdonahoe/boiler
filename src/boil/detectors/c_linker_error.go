// Detector for C/C++ linker errors.
package detectors

// CLinkerErrorDetector detects C/C++ linker errors
type CLinkerErrorDetector struct {
	*BaseDetector
}

func NewCLinkerErrorDetector() (*CLinkerErrorDetector, error) {
	base, err := NewBaseDetector(
		"CLinkerErrorDetector",
		100,
		map[string]string{
			"linker_undefined_symbols": "undefined reference to [`'](?P<symbol>[^'`]+)[`']",
			"missing_file":             `/usr/bin/ld:.*?cannot find\s+(?P<file_path>[^\s:]+):\s+No such file or directory`,
		},
		[]DetectorExample{
			{
				Name:     "undefined_reference_backtick",
				Input:    "undefined reference to `ts_parser_new'",
				ClueType: "linker_undefined_symbols",
				Context:  map[string]string{"symbol": "ts_parser_new"},
			},
			{
				Name:     "undefined_reference_quote",
				Input:    "tree_print.c:(.text+0x137): undefined reference to 'ts_node_start_byte'",
				ClueType: "linker_undefined_symbols",
				Context:  map[string]string{"symbol": "ts_node_start_byte"},
			},
			{
				Name:     "ld_cannot_find",
				Input:    "/usr/bin/ld: cannot find exrecover.o: No such file or directory",
				ClueType: "missing_file",
				Context:  map[string]string{"file_path": "exrecover.o"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &CLinkerErrorDetector{base}, nil
}
