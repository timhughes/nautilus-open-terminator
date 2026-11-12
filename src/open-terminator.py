# -*- coding: UTF-8 -*-
# open-terminator.py
#
# This is a modified version of open-tilix.py from https://github.com/gnunn1/tilix
# It is released under the Mozilla Public License 2.0
import gettext
import os
import shlex
import sys
from subprocess import Popen
from urllib.parse import unquote, urlparse

from gi import Repository, require_version


def _require_nautilus():
    """Require the newest available Nautilus GI version."""
    versions = sorted(
        Repository.get_default().enumerate_versions("Nautilus"),
        key=lambda v: [int(p) for p in v.split(".") if p.isdigit()],
        reverse=True,
    )
    for ver in versions:
        try:
            if ver.startswith("3."):
                require_version("Gtk", "3.0")
            require_version("Nautilus", ver)
            return
        except ValueError:
            continue
    raise ValueError("Namespace Nautilus not available")


_require_nautilus()
from gi.repository import Gio, GObject, Nautilus

TERMINAL = "terminator"
REMOTE_URI_SCHEME = ["sftp"]
DOMAIN = "nautilus-open-terminator"


def _get_translator():
    """Return a gettext translation function for this extension."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    xdg_data_dirs = [
        d for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if d
    ]
    localedirs = [
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "locale"),
        os.path.join(xdg_data_home, "locale"),
        *[os.path.join(d, "locale") for d in xdg_data_dirs],
    ]
    for localedir in localedirs:
        if gettext.find(DOMAIN, localedir):
            return gettext.translation(DOMAIN, localedir=localedir, fallback=True).gettext
    return gettext.NullTranslations().gettext


_ = _get_translator()


def _checkdecode(s):
    """Decode string assuming utf encoding if it's bytes, else return unmodified"""

    return s.decode("utf-8") if isinstance(s, bytes) else s


def _launch(cmd):
    """Spawn a terminal subprocess without blocking Nautilus."""
    try:
        Popen(cmd)
    except OSError as err:
        sys.stderr.write("nautilus-open-terminator: failed to launch {}: {}\n".format(cmd[0], err))


class OpenTerminatorExtension(GObject.GObject, Nautilus.MenuProvider):
    def _open_terminal(self, file_):
        if file_.get_uri_scheme() in REMOTE_URI_SCHEME:
            result = urlparse(file_.get_uri())
            if not result.hostname:
                _launch([TERMINAL])
                return

            try:
                port = result.port
            except ValueError:
                port = None

            target = (
                "{0}@{1}".format(unquote(result.username), result.hostname)
                if result.username
                else result.hostname
            )
            cmd = [TERMINAL, "-x", "ssh", "-t"]
            if port is not None and 1 <= port <= 65535:
                cmd.extend(["-p", str(port)])
            cmd.extend(["--", target])

            if file_.is_directory() and result.path:
                remote_path = unquote(result.path)
                cmd.append("cd -- {0} && exec $SHELL".format(shlex.quote(remote_path)))

            _launch(cmd)
        else:
            filename = Gio.File.new_for_uri(file_.get_uri()).get_path()
            if filename:
                _launch([TERMINAL, "--working-directory", filename])
            else:
                _launch([TERMINAL])

    def _menu_activate_cb(self, menu, file_):
        self._open_terminal(file_)

    def get_file_items(self, *args):
        files = args[-1] if args else []
        if len(files) != 1:
            return []
        items = []
        file_ = files[0]

        if file_.is_directory():
            if file_.get_uri_scheme() in REMOTE_URI_SCHEME:
                uri = _checkdecode(file_.get_uri())
                item = Nautilus.MenuItem(
                    name="NautilusPython::open_remote_item",
                    label=_("Open Remote Terminator"),
                    tip=_("Open Remote Terminator In {}").format(uri),
                )
            else:
                filename = _checkdecode(file_.get_name())
                item = Nautilus.MenuItem(
                    name="NautilusPython::open_file_item",
                    label=_("Open In Terminator"),
                    tip=_("Open Terminator In {}").format(filename),
                )
            item.connect("activate", self._menu_activate_cb, file_)
            items.append(item)

        return items

    def get_background_items(self, *args):
        if not args:
            return []
        file_ = args[-1]
        items = []

        if file_.get_uri_scheme() in REMOTE_URI_SCHEME:
            item = Nautilus.MenuItem(
                name="NautilusPython::open_bg_remote_item",
                label=_("Open Remote Terminator Here"),
                tip=_("Open Remote Terminator In This Directory"),
            )
        else:
            item = Nautilus.MenuItem(
                name="NautilusPython::open_bg_file_item",
                label=_("Open Terminator Here"),
                tip=_("Open Terminator In This Directory"),
            )
        item.connect("activate", self._menu_activate_cb, file_)
        items.append(item)

        return items
