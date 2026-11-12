import gettext
import glob
import importlib.util
import io
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
MODULE_PATH = os.path.join(REPO_ROOT, "src", "open-terminator.py")


def _load_extension_module(
    require_version_side_effect=None,
    env_overrides=None,
    available_nautilus_versions=("4.1", "4.0"),
):
    """Load src/open-terminator.py with mocked gi/Nautilus bindings and isolated env."""
    gi = types.ModuleType("gi")
    gi.require_version = MagicMock(side_effect=require_version_side_effect)
    repo = MagicMock()
    repo.enumerate_versions.return_value = list(available_nautilus_versions)
    gi.Repository = types.SimpleNamespace(get_default=MagicMock(return_value=repo))

    class _GObjectBase:
        pass

    class _MenuProviderBase:
        pass

    class _FakeMenuItem:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.connections = []

        def connect(self, signal, callback, *args):
            self.connections.append((signal, callback, args))

    gi_repo = types.ModuleType("gi.repository")
    gi_repo.Gio = MagicMock()
    gi_repo.GObject = types.SimpleNamespace(GObject=_GObjectBase)
    gi_repo.Nautilus = types.SimpleNamespace(
        MenuProvider=_MenuProviderBase,
        MenuItem=_FakeMenuItem,
    )

    clean_env = {"PATH": os.environ.get("PATH", ""), "HOME": "/nonexistent", "LC_ALL": "C"}
    if env_overrides:
        clean_env.update(env_overrides)

    with patch.dict(os.environ, clean_env, clear=True), patch.dict(
        sys.modules, {"gi": gi, "gi.repository": gi_repo}
    ):
        spec = importlib.util.spec_from_file_location("open_terminator", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, gi, gi_repo


class TestOpenTerminatorExtension(unittest.TestCase):
    def setUp(self):
        self.mod, self.gi, self.gi_repo = _load_extension_module()
        self.ext = self.mod.OpenTerminatorExtension()

    def _make_file(self, uri, scheme="file", is_dir=True, name="dir"):
        f = MagicMock()
        f.get_uri.return_value = uri
        f.get_uri_scheme.return_value = scheme
        f.is_directory.return_value = is_dir
        f.get_name.return_value = name
        return f

    def test_nautilus_version_fallback_on_import(self):
        # Picks newest enumerated version (e.g. 4.2 over 4.10? 4.10 > 4.2 numerically)
        calls_410 = []
        _load_extension_module(
            require_version_side_effect=lambda ns, ver: calls_410.append((ns, ver)),
            available_nautilus_versions=("4.0", "4.2", "4.10"),
        )
        self.assertEqual(calls_410, [("Nautilus", "4.10")])

        # Nautilus 4.1 -> 4.0 fallback when 4.1 raises ValueError
        calls_40 = []

        def require_40(ns, ver):
            calls_40.append((ns, ver))
            if (ns, ver) == ("Nautilus", "4.1"):
                raise ValueError("Nautilus 4.1 not available")

        _load_extension_module(
            require_version_side_effect=require_40,
            available_nautilus_versions=("4.0", "4.1"),
        )
        self.assertEqual(calls_40, [("Nautilus", "4.1"), ("Nautilus", "4.0")])

        # Nautilus 3.0 requires Gtk 3.0
        calls_30 = []
        _load_extension_module(
            require_version_side_effect=lambda ns, ver: calls_30.append((ns, ver)),
            available_nautilus_versions=("3.0",),
        )
        self.assertEqual(calls_30, [("Gtk", "3.0"), ("Nautilus", "3.0")])

        # Empty enumerate_versions or all versions failing raises ValueError immediately
        with self.assertRaisesRegex(ValueError, "Namespace Nautilus not available"):
            _load_extension_module(available_nautilus_versions=())

        def fail_all(ns, ver):
            raise ValueError(f"{ns} {ver} unavailable")

        with self.assertRaisesRegex(ValueError, "Namespace Nautilus not available"):
            _load_extension_module(
                require_version_side_effect=fail_all,
                available_nautilus_versions=("4.1",),
            )

    def test_get_translator_xdg_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            xdg_home = os.path.join(tmpdir, "xdg_home")
            xdg_sys = os.path.join(tmpdir, "xdg_sys")
            with patch.dict(
                os.environ,
                {"XDG_DATA_HOME": xdg_home, "XDG_DATA_DIRS": f":{xdg_sys}:"},
                clear=True,
            ), patch.object(self.mod.gettext, "find", return_value=None) as find_mock:
                tr = self.mod._get_translator()
                self.assertEqual(tr("Open In Terminator"), "Open In Terminator")
                checked_dirs = [c.args[1] for c in find_mock.call_args_list]
                self.assertIn(os.path.join(xdg_home, "locale"), checked_dirs)
                self.assertIn(os.path.join(xdg_sys, "locale"), checked_dirs)

            # Match on XDG_DATA_HOME returns translation object's gettext
            fake_tr = MagicMock()
            fake_tr.gettext.return_value = "Ouvrir dans Terminator"
            with patch.dict(
                os.environ, {"XDG_DATA_HOME": xdg_home}, clear=True
            ), patch.object(
                self.mod.gettext,
                "find",
                side_effect=lambda dom, d: "/fake.mo" if d == os.path.join(xdg_home, "locale") else None,
            ), patch.object(
                self.mod.gettext, "translation", return_value=fake_tr
            ) as trans_mock:
                tr = self.mod._get_translator()
                self.assertEqual(tr("Open In Terminator"), "Ouvrir dans Terminator")
                trans_mock.assert_called_once_with(
                    "nautilus-open-terminator",
                    localedir=os.path.join(xdg_home, "locale"),
                    fallback=True,
                )

    def test_checkdecode(self):
        self.assertEqual(self.mod._checkdecode(b"hello"), "hello")
        self.assertEqual(self.mod._checkdecode("world"), "world")

    def test_open_local_directory_with_spaces(self):
        f = self._make_file("file:///tmp/my%20dir")
        self.gi_repo.Gio.File.new_for_uri.return_value.get_path.return_value = "/tmp/my dir"
        with patch.object(self.mod, "Popen") as popen:
            self.ext._open_terminal(f)
            popen.assert_called_once_with(["terminator", "--working-directory", "/tmp/my dir"])

    def test_open_ftp_falls_back_to_plain_terminator(self):
        f = self._make_file("ftp://example.com/pub", scheme="ftp")
        self.gi_repo.Gio.File.new_for_uri.return_value.get_path.return_value = None
        with patch.object(self.mod, "Popen") as popen:
            self.ext._open_terminal(f)
            popen.assert_called_once_with(["terminator"])

    def test_open_sftp_with_user_port_and_encoded_path(self):
        f = self._make_file("sftp://alice%20smith@example.com:2222/my%20dir/sub", scheme="sftp")
        with patch.object(self.mod, "Popen") as popen:
            self.ext._open_terminal(f)
            popen.assert_called_once_with(
                [
                    "terminator",
                    "-x",
                    "ssh",
                    "-t",
                    "-p",
                    "2222",
                    "--",
                    "alice smith@example.com",
                    "cd -- '/my dir/sub' && exec $SHELL",
                ]
            )

    def test_open_sftp_shell_metacharacters_quoted(self):
        f = self._make_file("sftp://example.com/tmp/a'b%3Bid", scheme="sftp")
        with patch.object(self.mod, "Popen") as popen:
            self.ext._open_terminal(f)
            popen.assert_called_once_with(
                [
                    "terminator",
                    "-x",
                    "ssh",
                    "-t",
                    "--",
                    "example.com",
                    "cd -- '/tmp/a'\"'\"'b;id' && exec $SHELL",
                ]
            )

    def test_open_sftp_without_path_or_non_dir(self):
        f_no_path = self._make_file("sftp://example.com", scheme="sftp", is_dir=True)
        f_non_dir = self._make_file("sftp://example.com/file.txt", scheme="sftp", is_dir=False)
        with patch.object(self.mod, "Popen") as popen:
            self.ext._open_terminal(f_no_path)
            popen.assert_called_with(["terminator", "-x", "ssh", "-t", "--", "example.com"])
            self.ext._open_terminal(f_non_dir)
            popen.assert_called_with(["terminator", "-x", "ssh", "-t", "--", "example.com"])

    def test_open_sftp_missing_hostname_falls_back(self):
        f = self._make_file("sftp:///only/path", scheme="sftp")
        with patch.object(self.mod, "Popen") as popen:
            self.ext._open_terminal(f)
            popen.assert_called_once_with(["terminator"])

    def test_open_sftp_port_validation_and_boundaries(self):
        for uri in (
            "sftp://example.com:abc/tmp",
            "sftp://example.com:0/tmp",
            "sftp://example.com:99999/tmp",
        ):
            f = self._make_file(uri, scheme="sftp")
            with patch.object(self.mod, "Popen") as popen:
                self.ext._open_terminal(f)
                popen.assert_called_once_with(
                    [
                        "terminator",
                        "-x",
                        "ssh",
                        "-t",
                        "--",
                        "example.com",
                        "cd -- /tmp && exec $SHELL",
                    ]
                )

        for valid_port in ("1", "65535"):
            f = self._make_file(f"sftp://example.com:{valid_port}/tmp", scheme="sftp")
            with patch.object(self.mod, "Popen") as popen:
                self.ext._open_terminal(f)
                popen.assert_called_once_with(
                    [
                        "terminator",
                        "-x",
                        "ssh",
                        "-t",
                        "-p",
                        valid_port,
                        "--",
                        "example.com",
                        "cd -- /tmp && exec $SHELL",
                    ]
                )

    def test_launch_handles_missing_binary(self):
        stderr = io.StringIO()
        with patch.object(self.mod, "Popen", side_effect=FileNotFoundError("not found")), patch.object(
            sys, "stderr", stderr
        ):
            self.mod._launch(["terminator"])
        self.assertIn("failed to launch terminator", stderr.getvalue())

    def test_get_file_items_local_and_remote_nautilus_3_and_4(self):
        d = self._make_file("file:///tmp/work", name=b"work")
        remote = self._make_file(b"sftp://host/srv", scheme="sftp")
        regular_file = self._make_file("file:///tmp/a.txt", is_dir=False, name="a.txt")

        self.assertEqual(self.ext.get_file_items(), [])
        self.assertEqual(self.ext.get_file_items([]), [])
        self.assertEqual(self.ext.get_file_items(None, [d, regular_file]), [])
        self.assertEqual(self.ext.get_file_items([regular_file]), [])

        for items in (self.ext.get_file_items([d]), self.ext.get_file_items(None, [d])):
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].kwargs["name"], "NautilusPython::open_file_item")
            self.assertEqual(items[0].kwargs["label"], "Open In Terminator")
            self.assertEqual(items[0].kwargs["tip"], "Open Terminator In work")
            signal, cb, args = items[0].connections[0]
            self.assertEqual(signal, "activate")
            self.assertEqual(args, (d,))
            with patch.object(self.ext, "_open_terminal") as open_term:
                cb(items[0], *args)
                open_term.assert_called_once_with(d)

        for items in (self.ext.get_file_items([remote]), self.ext.get_file_items(None, [remote])):
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].kwargs["name"], "NautilusPython::open_remote_item")
            self.assertEqual(items[0].kwargs["label"], "Open Remote Terminator")
            self.assertEqual(items[0].kwargs["tip"], "Open Remote Terminator In sftp://host/srv")
            signal, cb, args = items[0].connections[0]
            self.assertEqual(signal, "activate")
            self.assertEqual(args, (remote,))
            with patch.object(self.ext, "_open_terminal") as open_term:
                cb(items[0], *args)
                open_term.assert_called_once_with(remote)

    def test_get_background_items_local_and_remote(self):
        local = self._make_file("file:///tmp")
        remote = self._make_file("sftp://host/tmp", scheme="sftp")

        self.assertEqual(self.ext.get_background_items(), [])

        bg_local = self.ext.get_background_items(local)
        self.assertEqual(len(bg_local), 1)
        self.assertEqual(bg_local[0].kwargs["name"], "NautilusPython::open_bg_file_item")
        self.assertEqual(bg_local[0].kwargs["label"], "Open Terminator Here")
        self.assertEqual(bg_local[0].kwargs["tip"], "Open Terminator In This Directory")
        signal, cb, args = bg_local[0].connections[0]
        self.assertEqual(signal, "activate")
        with patch.object(self.ext, "_open_terminal") as open_term:
            cb(bg_local[0], *args)
            open_term.assert_called_once_with(local)

        bg_remote = self.ext.get_background_items(None, remote)
        self.assertEqual(len(bg_remote), 1)
        self.assertEqual(bg_remote[0].kwargs["name"], "NautilusPython::open_bg_remote_item")
        self.assertEqual(bg_remote[0].kwargs["label"], "Open Remote Terminator Here")
        self.assertEqual(bg_remote[0].kwargs["tip"], "Open Remote Terminator In This Directory")
        signal, cb, args = bg_remote[0].connections[0]
        self.assertEqual(signal, "activate")
        with patch.object(self.ext, "_open_terminal") as open_term:
            cb(bg_remote[0], *args)
            open_term.assert_called_once_with(remote)


class TestTranslations(unittest.TestCase):
    def test_compiled_locales_if_present(self):
        localedir = os.path.join(REPO_ROOT, "locale")
        if not os.path.isdir(localedir):
            self.skipTest("locale/ not built")

        expected_strings = [
            "Open In Terminator",
            "Open Terminator In {}",
            "Open Terminator Here",
            "Open Terminator In This Directory",
            "Open Remote Terminator",
            "Open Remote Terminator In {}",
            "Open Remote Terminator Here",
            "Open Remote Terminator In This Directory",
        ]
        langs = sorted(
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(REPO_ROOT, "po", "*.po"))
        )
        self.assertGreater(len(langs), 0)
        for lang in langs:
            t = gettext.translation("nautilus-open-terminator", localedir=localedir, languages=[lang])
            for s in expected_strings:
                translated = t.gettext(s)
                self.assertTrue(translated and translated != s, f"{lang} missing {s!r}")
                if "{}" in s:
                    self.assertNotEqual(translated.format("dir"), translated)


if __name__ == "__main__":
    unittest.main()
