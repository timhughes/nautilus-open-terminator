# -*- coding: UTF-8 -*-
# open-terminator.py
#
# This is a modified version of open-tilix.py from https://github.com/gnunn1/tilix
# It is released under the Mozilla Public License 2.0
from gettext import gettext, textdomain
from subprocess import PIPE, call
from typing import List

try:
    from urllib import unquote
    from urlparse import urlparse
except ImportError:
    from urllib.parse import unquote, urlparse

from gi import require_version

require_version("Gtk", "4.0")
require_version("Nautilus", "4.0")
from gi.repository import Gio, GObject, Gtk, Nautilus

TERMINAL = "terminator"
REMOTE_URI_SCHEME = ["ftp", "sftp"]
textdomain("terminator")
_ = gettext


def _checkdecode(s):
    """
    Decode string assuming utf encoding if it's bytes, else return
    unmodified
    """

    return s.decode("utf-8") if isinstance(s, bytes) else s


class OpenTerminatorExtension(GObject.GObject, Nautilus.MenuProvider):
    def _open_terminal(
        self,
        file: Nautilus.FileInfo,
    ) -> None:
        if file.get_uri_scheme() in REMOTE_URI_SCHEME:
            result = urlparse(file.get_uri())

            if result.username:
                value = "ssh -t {0}@{1}".format(
                    result.username,
                    result.hostname,
                )
            else:
                value = "ssh -t {0}".format(result.hostname)

            if result.port:
                value = "{0} -p {1}".format(value, result.port)

            if file.is_directory():
                value = "{0} 'cd \"{1}\" ; $SHELL'".format(value, result.path)
            call('{0} -e "{1}" &'.format(TERMINAL, value), shell=True)
        else:
            filename = Gio.File.new_for_uri(file.get_uri()).get_path()
            if filename:
                call(
                    '{0} --working-directory "{1}" &'.format(
                        TERMINAL,
                        filename,
                    ),
                    shell=True,
                )
            else:
                call("{0} &".format(TERMINAL), shell=True)

    def _menu_activate_cb(
        self,
        menu: Nautilus.MenuItem,
        file: Nautilus.FileInfo,
    ) -> None:
        self._open_terminal(file)

    def _menu_background_activate_cb(
        self,
        menu: Nautilus.MenuItem,
        file: Nautilus.FileInfo,
    ) -> None:
        self._open_terminal(file)

    def get_file_items(
        self,
        files: List[Nautilus.FileInfo],
    ) -> List[Nautilus.MenuItem]:
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
                item.connect("activate", self._menu_activate_cb, file_)
                items.append(item)
            else:
                filename = _checkdecode(file_.get_name())
                item = Nautilus.MenuItem(
                    name="NautilusPython::open_file_item",
                    label=_("Open In Terminator"),
                    tip=_("Open Terminator In {}").format(filename),
                )
                item.connect(
                    "activate",
                    self._menu_activate_cb,
                    file_,
                )
                items.append(item)

        return items

    def get_background_items(
        self,
        current_folder: Nautilus.FileInfo,
    ) -> List[Nautilus.MenuItem]:

        items = []

        if current_folder.get_uri_scheme() in REMOTE_URI_SCHEME:
            item = Nautilus.MenuItem(
                name="NautilusPython::open_bg_remote_item",
                label=_("Open Remote Terminator Here"),
                tip=_("Open Remote Terminator In This Directory"),
            )
            item.connect("activate", self._menu_activate_cb, current_folder)
            items.append(item)
        else:
            item = Nautilus.MenuItem(
                name="NautilusPython::open_bg_file_item",
                label=_("Open Terminator Here"),
                tip=_("Open Terminator In This Directory"),
            )
            item.connect(
                "activate",
                self._menu_background_activate_cb,
                current_folder,
            )
            items.append(item)

        return items
