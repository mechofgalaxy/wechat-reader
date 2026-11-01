package main

import (
	"fmt"
	"syscall"
	"testing"
)

func TestReaderStopGuards(t *testing.T) {
	oldOwner, oldPIDs, oldOutput, oldSignal := readerOwner, readerPIDs, readerOutput, readerSignal
	defer func() { readerOwner, readerPIDs, readerOutput, readerSignal = oldOwner, oldPIDs, oldOutput, oldSignal }()
	readerOwner = func() (int, int, bool) { return 501, 20, true }
	official := "/Applications/WeChat.app"
	for _, tc := range []struct{ name, observed string }{
		{"foreign owner", "502 /Applications/WeChat.app/Contents/MacOS/WeChat"},
		{"other installation", "501 /Applications/WeChat2.app/Contents/MacOS/WeChat"},
		{"malformed identity", "PRIVATE-NON-IDENTITY"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			readerPIDs = func() ([]int, error) { return []int{123}, nil }
			readerOutput = func(int) ([]byte, error) { return []byte(tc.observed), nil }
			readerSignal = func(int, syscall.Signal) error { t.Fatal("must not signal an unverified process"); return nil }
			if _, err := readerStopWeChat([]string{official}); err == nil {
				t.Fatal("expected scope rejection")
			}
		})
	}
	t.Run("identity changes before signal", func(t *testing.T) {
		reads := 0
		readerPIDs = func() ([]int, error) { return []int{123}, nil }
		readerOutput = func(int) ([]byte, error) {
			reads++
			if reads == 1 {
				return []byte("501 /Applications/WeChat.app/Contents/MacOS/WeChat"), nil
			}
			return nil, fmt.Errorf("gone")
		}
		readerSignal = func(int, syscall.Signal) error { t.Fatal("must recheck before signal"); return nil }
		if _, err := readerStopWeChat([]string{official}); err == nil {
			t.Fatal("expected recheck rejection")
		}
	})
	t.Run("verified owner uses only SIGTERM", func(t *testing.T) {
		signals := 0
		readerPIDs = func() ([]int, error) {
			if signals == 0 {
				return []int{123}, nil
			}
			return nil, nil
		}
		readerOutput = func(int) ([]byte, error) { return []byte("501 /Applications/WeChat.app/Contents/MacOS/WeChat"), nil }
		readerSignal = func(pid int, sig syscall.Signal) error {
			if pid != 123 || sig != syscall.SIGTERM {
				t.Fatal("wrong signal")
			}
			signals++
			return nil
		}
		running, err := readerStopWeChat([]string{official})
		if err != nil || !running || signals != 1 {
			t.Fatalf("stop failed: %v", err)
		}
	})
}

func TestReaderPasswordPathsDisabled(t *testing.T) {
	if _, err := readStoredSudoPassword(); err == nil {
		t.Fatal("password reading enabled")
	}
	if err := storeSudoPassword("fictional"); err == nil {
		t.Fatal("password storage enabled")
	}
	if _, err := promptSudoPasswordGUI(); err == nil {
		t.Fatal("password prompt enabled")
	}
	if err := reExecElevated(); err == nil {
		t.Fatal("automatic elevation enabled")
	}
	if _, err := runCodesignWeChat(); err == nil {
		t.Fatal("original application signing enabled")
	}
}
