Name:           nautilus-open-terminator
Version:        0.1.0
Release:        1%{?dist}
Summary:        Open Terminator from the Nautilus context menu

License:        MPL-2.0
URL:            https://github.com/timhughes/nautilus-open-terminator
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  appstream
BuildRequires:  gettext
BuildRequires:  make
BuildRequires:  python3

Requires:       nautilus-python
Requires:       python3
Requires:       terminator

%description
A Nautilus (GNOME Files) extension that adds "Open In Terminator" and
"Open Terminator Here" entries to the right-click context menu for local
directories and remote SFTP locations.

%prep
%autosetup

%build
%make_build

%install
%make_install PREFIX=%{_prefix}
%find_lang %{name}

%check
python3 -B -m py_compile src/open-terminator.py
python3 -B -m unittest discover -s tests -v
appstreamcli validate --no-net %{buildroot}%{_datadir}/metainfo/io.github.timhughes.nautilus_open_terminator.metainfo.xml

%files -f %{name}.lang
%license LICENSE
%doc README.md
%{_datadir}/nautilus-python/extensions/open-terminator.py
%{_datadir}/metainfo/io.github.timhughes.nautilus_open_terminator.metainfo.xml

%changelog
* Thu Nov 12 2026 Tim Hughes <thughes@thegoldfish.org> - 0.1.0-1
- Initial packaged release with multi-language translations and SFTP fixes
