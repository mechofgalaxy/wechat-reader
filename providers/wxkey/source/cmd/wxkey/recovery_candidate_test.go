package main

import (
	"os/exec"
	"testing"
)

func TestFailureUnwindsCleanup(t *testing.T) {
	cleaned := false
	code := failureExit(func() {
		defer func() { cleaned = true }()
		fail("synthetic failure")
	})
	if code != 1 || !cleaned {
		t.Fatalf("code=%d cleanup=%v", code, cleaned)
	}
}

func TestSuccessfulCommandReturnsZero(t *testing.T) {
	if code := failureExit(func() {}); code != 0 {
		t.Fatalf("code=%d", code)
	}
}

func TestUnexpectedPanicNotHidden(t *testing.T) {
	defer func() {
		if recover() != "unexpected" {
			t.Fatal("unexpected panic was swallowed")
		}
	}()
	failureExit(func() { panic("unexpected") })
}

func TestLaunchCandidateIsolated(t *testing.T) {
	out, err := exec.Command("/usr/bin/python3", "../../tests/test_launch_candidate.py", "-v").CombinedOutput()
	if err != nil {
		t.Fatalf("isolated launch tests: %v\n%s", err, out)
	}
}
