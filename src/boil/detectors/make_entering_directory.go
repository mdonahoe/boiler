// Detector for make entering directory messages.
package detectors

// MakeEnteringDirectoryDetector detects make entering directory messages
type MakeEnteringDirectoryDetector struct {
	*BaseDetector
}

func NewMakeEnteringDirectoryDetector() (*MakeEnteringDirectoryDetector, error) {
	base, err := NewBaseDetector(
		"MakeEnteringDirectoryDetector",
		100,
		map[string]string{
			"make_enter_directory": `make(?:\[\d+\])?: Entering directory '(?P<directory>[^']+)'`,
		},
		[]DetectorExample{
			{
				Name:     "make_entering_simple",
				Input:    "make: Entering directory '/home/user/project'",
				ClueType: "make_enter_directory",
				Context:  map[string]string{"directory": "/home/user/project"},
			},
			{
				Name:     "make_entering_with_level",
				Input:    "make[1]: Entering directory '/tmp/build'",
				ClueType: "make_enter_directory",
				Context:  map[string]string{"directory": "/tmp/build"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &MakeEnteringDirectoryDetector{base}, nil
}
