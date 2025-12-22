// Detector for permission denied errors.
package detectors

// PermissionDeniedDetector detects permission denied errors
type PermissionDeniedDetector struct {
	*BaseDetector
}

func NewPermissionDeniedDetector() (*PermissionDeniedDetector, error) {
	base, err := NewBaseDetector(
		"PermissionDeniedDetector",
		100,
		map[string]string{
			"py_permission_denied": `Permission denied:\s*['"]?(?P<file_path>[^'"]+)['"]?`,
			"sh_permission_denied": `:\s*(?P<file_path>[^:]+):\s*Permission denied`,
		},
		[]DetectorExample{
			{
				Name:     "python_permission_denied",
				Input:    "Permission denied: '/etc/passwd'",
				ClueType: "py_permission_denied",
				Context:  map[string]string{"file_path": "/etc/passwd"},
			},
			{
				Name:     "shell_permission_denied",
				Input:    "bash: /root/script.sh: Permission denied",
				ClueType: "sh_permission_denied",
				Context:  map[string]string{"file_path": "/root/script.sh"},
			},
		},
	)
	if err != nil {
		return nil, err
	}
	return &PermissionDeniedDetector{base}, nil
}
