// Session management for the current boiling invocation
package core

// Session represents common properties of the current boiling invocation
type Session struct {
	Key             string
	GitRef          string
	Iteration       int
	Command         []string
	SearchMode      bool            // True during Phase 2 of --search (element-level restoration)
	DiscoveredFiles map[string]bool // Files discovered during Phase 1 of --search
}

// currentSession is the global session instance
var currentSession = &Session{
	Key:             "",
	GitRef:          "HEAD",
	Iteration:       0,
	Command:         []string{},
	SearchMode:      false,
	DiscoveredFiles: make(map[string]bool),
}

// Ctx returns the current session
func Ctx() *Session {
	return currentSession
}

// NewSession creates and sets a new current session
func NewSession(key, gitRef string, iteration int, command []string) {
	currentSession = &Session{
		Key:             key,
		GitRef:          gitRef,
		Iteration:       iteration,
		Command:         command,
		SearchMode:      false,
		DiscoveredFiles: make(map[string]bool),
	}
}

// SetSearchMode enables search mode for Phase 2 of --search
func SetSearchMode(enabled bool) {
	currentSession.SearchMode = enabled
}

// AddDiscoveredFile records a file that was restored during Phase 1
func AddDiscoveredFile(filePath string) {
	if currentSession.DiscoveredFiles == nil {
		currentSession.DiscoveredFiles = make(map[string]bool)
	}
	currentSession.DiscoveredFiles[filePath] = true
}

// IsDiscoveredFile checks if a file was discovered during Phase 1
func IsDiscoveredFile(filePath string) bool {
	if currentSession.DiscoveredFiles == nil {
		return false
	}
	return currentSession.DiscoveredFiles[filePath]
}

// ClearDiscoveredFiles resets the discovered files map
func ClearDiscoveredFiles() {
	currentSession.DiscoveredFiles = make(map[string]bool)
}
