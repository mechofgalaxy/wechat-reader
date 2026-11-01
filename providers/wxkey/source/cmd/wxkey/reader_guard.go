package main

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

var readerOwner = invokingUserIDs
var readerPIDs = wechatPIDs
var readerOutput = func(pid int) ([]byte, error) {
	return exec.Command("/bin/ps", "-p", strconv.Itoa(pid), "-o", "uid=,comm=").Output()
}
var readerSignal = syscall.Kill

// A single verified owner's exact WeChat executable, never a global killall.
func readerProcess(pid int, apps []string) error {
	uid, _, ok := readerOwner()
	if !ok || uid <= 0 {
		return fmt.Errorf("target_identity_unverified")
	}
	out, err := readerOutput(pid)
	if err != nil {
		return fmt.Errorf("wechat_process_unverified")
	}
	fields := strings.Fields(string(out))
	if len(fields) < 2 || fields[0] != strconv.Itoa(uid) {
		return fmt.Errorf("other_user_wechat_running")
	}
	executable := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(string(out)), fields[0]))
	for _, app := range apps {
		if executable == filepath.Join(app, "Contents", "MacOS", "WeChat") {
			return nil
		}
	}
	return fmt.Errorf("other_wechat_install_running")
}

func readerStopWeChat(apps []string) (bool, error) {
	pids, err := readerPIDs()
	if err != nil {
		return false, fmt.Errorf("official_wechat_scan_failed")
	}
	// Validate the entire set before touching any process.
	for _, pid := range pids {
		if err := readerProcess(pid, apps); err != nil {
			return false, err
		}
	}
	for _, pid := range pids {
		if err := readerProcess(pid, apps); err != nil {
			return true, err
		}
		if err := readerSignal(pid, syscall.SIGTERM); err != nil && err != syscall.ESRCH {
			return true, err
		}
	}
	deadline := time.Now().Add(8 * time.Second)
	for time.Now().Before(deadline) {
		left, err := readerPIDs()
		if err != nil {
			return len(pids) > 0, err
		}
		if len(left) == 0 {
			return len(pids) > 0, nil
		}
		for _, pid := range left {
			if err := readerProcess(pid, apps); err != nil {
				return true, err
			}
		}
		time.Sleep(200 * time.Millisecond)
	}
	return len(pids) > 0, fmt.Errorf("official_wechat_stop_failed")
}
