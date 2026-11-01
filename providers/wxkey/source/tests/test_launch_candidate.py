"""Lifecycle tests using fakes only. No WeChat access or privileged execution."""

import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "cmd/wxkey/main.go"
PROBE = SOURCE.read_text().split("const pbkdfProbePython = `", 1)[1].split("`", 1)[0]
NAMES = {"owner_launch_info", "verify_process_owner", "wait_for_stop", "launch_as_owner"}
FUNCTIONS = ast.Module(body=[node for node in ast.parse(PROBE).body
                           if isinstance(node, ast.FunctionDef) and node.name in NAMES], type_ignores=[])


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.launch = Mock()
        self.launch.GetLaunchFlags.return_value = 0
        self.listener = Mock()
        self.lldb = NS(SBLaunchInfo=lambda _: self.launch, eLaunchFlagStopAtEntry=4,
                       SBListener=lambda _: self.listener, SBEvent=lambda: object(),
                       SBError=lambda: NS(Fail=lambda: False), eStateStopped=5,
                       eStateExited=10, eStateCrashed=8, eStateDetached=9)
        self.os = NS(environ={"WXKEY_ORIG_HOME": "/example-home/user", "HOME": "/root"},
                     path=NS(expanduser=lambda _: "/root"), stat=lambda _: NS(st_uid=501))
        self.clock = Mock(return_value=0)
        self.ns = {"lldb": self.lldb, "os": self.os, "time": NS(monotonic=self.clock),
                   "pwd": NS(getpwuid=lambda _: NS(pw_gid=20, pw_name="user"))}
        exec(compile(FUNCTIONS, "launch_candidate", "exec"), self.ns)
        self.info = NS(IsValid=lambda: True, UserIDIsValid=lambda: True,
                       EffectiveUserIDIsValid=lambda: True, GroupIDIsValid=lambda: True,
                       EffectiveGroupIDIsValid=lambda: True, GetUserID=lambda: 501,
                       GetEffectiveUserID=lambda: 501, GetGroupID=lambda: 20,
                       GetEffectiveGroupID=lambda: 20)
        self.process = Mock()
        self.process.IsValid.return_value = True
        self.process.GetState.return_value = 5
        self.process.GetStopID.return_value = 1
        self.process.GetProcessInfo.return_value = self.info
        self.target = NS(Launch=lambda *_: self.process)

    def test_uid_gid_and_environment_explicit(self):
        _, uid, gid = self.ns["owner_launch_info"]("/example-home/user/account")
        self.assertEqual((uid, gid), (501, 20))
        self.launch.SetUserID.assert_called_once_with(501)
        self.launch.SetGroupID.assert_called_once_with(20)
        entries, append = self.launch.SetEnvironmentEntries.call_args.args
        self.assertFalse(append)
        self.assertIn("HOME=/example-home/user", entries)
        self.assertIn("LOGNAME=user", entries)
        self.launch.SetLaunchFlags.assert_called_once_with(4)

    def test_root_owner_rejected(self):
        self.os.stat = lambda _: NS(st_uid=0)
        with self.assertRaisesRegex(RuntimeError, "identity_unverified"):
            self.ns["owner_launch_info"]("/account")

    def test_other_account_owner_rejected(self):
        self.os.stat = lambda path: NS(st_uid=501 if path == "/example-home/user" else 502)
        with self.assertRaisesRegex(RuntimeError, "identity_unverified"):
            self.ns["owner_launch_info"]("/account")

    def test_actual_root_process_killed_before_return(self):
        self.info.GetEffectiveUserID = lambda: 0
        with self.assertRaisesRegex(RuntimeError, "identity_mismatch"):
            self.ns["launch_as_owner"](self.target, "/account", 10)
        self.process.Kill.assert_called_once()
        self.process.Continue.assert_not_called()

    def test_unknown_identity_killed(self):
        self.info.EffectiveUserIDIsValid = lambda: False
        with self.assertRaisesRegex(RuntimeError, "identity_unverified"):
            self.ns["launch_as_owner"](self.target, "/account", 10)
        self.process.Kill.assert_called_once()

    def test_group_mismatch_rejected(self):
        self.info.GetEffectiveGroupID = lambda: 0
        with self.assertRaisesRegex(RuntimeError, "identity_mismatch"):
            self.ns["verify_process_owner"](self.process, 501, 20)

    def test_valid_launch_does_not_continue_before_caller(self):
        process, listener = self.ns["launch_as_owner"](self.target, "/account", 10)
        self.assertIs(process, self.process)
        self.assertIs(listener, self.listener)
        self.process.Continue.assert_not_called()
        self.process.Kill.assert_not_called()

    def test_launch_error_kills_valid_target(self):
        self.lldb.SBError = lambda: NS(Fail=lambda: True)
        with self.assertRaisesRegex(RuntimeError, "launch_failed"):
            self.ns["launch_as_owner"](self.target, "/account", 10)
        self.process.Kill.assert_called_once()

    def test_running_process_wait_has_deadline(self):
        self.process.GetState.return_value = 6
        self.clock.side_effect = [0, 1, 2, 3]
        self.assertFalse(self.ns["wait_for_stop"](self.process, self.listener, 3))
        self.assertEqual(self.listener.WaitForEvent.call_count, 3)
        self.assertTrue(all(call.args[0] == 1 for call in self.listener.WaitForEvent.call_args_list))

    def test_repeated_stop_is_not_handled_twice(self):
        self.clock.side_effect = [0, 1, 2]
        self.assertFalse(self.ns["wait_for_stop"](self.process, self.listener, 2, previous_stop=1))
        self.assertEqual(self.listener.WaitForEvent.call_count, 2)

    def test_exited_process_does_not_spin(self):
        self.process.GetState.return_value = 10
        self.assertFalse(self.ns["wait_for_stop"](self.process, self.listener, 10))
        self.listener.WaitForEvent.assert_not_called()

    def test_entry_timeout_kills_target(self):
        self.clock.return_value = 11
        with self.assertRaisesRegex(RuntimeError, "entry_timeout"):
            self.ns["launch_as_owner"](self.target, "/account", 10)
        self.process.Kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
