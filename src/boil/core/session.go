// Session management for the current boiling invocation
package core

// Session represents common properties of the current boiling invocation
type Session struct {
	Key       string
	GitRef    string
	Iteration int
	Command   []string
}

// currentSession is the global session instance
var currentSession = &Session{
	Key:       "",
	GitRef:    "HEAD",
	Iteration: 0,
	Command:   []string{},
}

// Ctx returns the current session
func Ctx() *Session {
	return currentSession
}

// NewSession creates and sets a new current session
func NewSession(key, gitRef string, iteration int, command []string) {
	currentSession = &Session{
		Key:       key,
		GitRef:    gitRef,
		Iteration: iteration,
		Command:   command,
	}
}
