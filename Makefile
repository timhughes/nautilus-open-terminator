DOMAIN = nautilus-open-terminator
APP_ID = io.github.timhughes.nautilus_open_terminator
VERSION ?= $(shell awk '/^Version:/ {print $$2}' nautilus-open-terminator.spec)
PREFIX ?= /usr
USER_DATA_DIR ?= $(or $(XDG_DATA_HOME),$(HOME)/.local/share)

PO_FILES = $(wildcard po/*.po)
LANGS = $(patsubst po/%.po,%,$(PO_FILES))
MO_FILES = $(patsubst po/%.po,locale/%/LC_MESSAGES/$(DOMAIN).mo,$(PO_FILES))

.PHONY: all pot check dist deb rpm arch install install-user uninstall uninstall-user clean distclean

all: $(MO_FILES)

locale/%/LC_MESSAGES/$(DOMAIN).mo: po/%.po
	@mkdir -p $(dir $@)
	msgfmt -o $@ $<

pot:
	xgettext --language=Python --keyword=_ --from-code=UTF-8 \
		--package-name=$(DOMAIN) \
		--output=po/$(DOMAIN).pot src/open-terminator.py

check: all
	python3 -B -m py_compile src/open-terminator.py
	python3 -B -m unittest discover -s tests -v
	@if command -v appstreamcli >/dev/null 2>&1; then \
		appstreamcli validate --no-net $(APP_ID).metainfo.xml; \
	fi

install-user: all
	install -Dm644 src/open-terminator.py $(USER_DATA_DIR)/nautilus-python/extensions/open-terminator.py
	install -Dm644 $(APP_ID).metainfo.xml $(USER_DATA_DIR)/metainfo/$(APP_ID).metainfo.xml
	@for lang in $(LANGS); do \
		install -Dm644 locale/$$lang/LC_MESSAGES/$(DOMAIN).mo \
			$(USER_DATA_DIR)/locale/$$lang/LC_MESSAGES/$(DOMAIN).mo; \
	done

install: all
	install -Dm644 src/open-terminator.py $(DESTDIR)$(PREFIX)/share/nautilus-python/extensions/open-terminator.py
	install -Dm644 $(APP_ID).metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	@for lang in $(LANGS); do \
		install -Dm644 locale/$$lang/LC_MESSAGES/$(DOMAIN).mo \
			$(DESTDIR)$(PREFIX)/share/locale/$$lang/LC_MESSAGES/$(DOMAIN).mo; \
	done

uninstall-user:
	rm -f $(USER_DATA_DIR)/nautilus-python/extensions/open-terminator.py
	rm -f $(USER_DATA_DIR)/metainfo/$(APP_ID).metainfo.xml
	@for lang in $(LANGS); do \
		rm -f $(USER_DATA_DIR)/locale/$$lang/LC_MESSAGES/$(DOMAIN).mo; \
	done

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/share/nautilus-python/extensions/open-terminator.py
	rm -f $(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	@for lang in $(LANGS); do \
		rm -f $(DESTDIR)$(PREFIX)/share/locale/$$lang/LC_MESSAGES/$(DOMAIN).mo; \
	done

dist:
	@mkdir -p dist
	tar --transform="s,^\.,$(DOMAIN)-$(VERSION)," \
		--exclude='.git' --exclude='locale' --exclude='dist' --exclude='__pycache__' --exclude='*.pyc' \
		-czf dist/$(DOMAIN)-$(VERSION).tar.gz .

deb:
	dpkg-buildpackage -us -uc -b -tc
	@mkdir -p dist
	mv ../$(DOMAIN)_*.deb dist/
	-mv ../$(DOMAIN)_*.buildinfo ../$(DOMAIN)_*.changes dist/ 2>/dev/null || true

rpm: dist
	@mkdir -p dist/rpmbuild/BUILD dist/rpmbuild/RPMS dist/rpmbuild/SOURCES dist/rpmbuild/SPECS dist/rpmbuild/SRPMS
	cp dist/$(DOMAIN)-$(VERSION).tar.gz dist/rpmbuild/SOURCES/
	rpmbuild --define "_topdir $(CURDIR)/dist/rpmbuild" -ba $(DOMAIN).spec
	cp dist/rpmbuild/RPMS/noarch/*.rpm dist/rpmbuild/SRPMS/*.rpm dist/

arch: dist
	@mkdir -p dist/archbuild
	cp PKGBUILD dist/$(DOMAIN)-$(VERSION).tar.gz dist/archbuild/
	cd dist/archbuild && PKGDEST="$(CURDIR)/dist" makepkg --nodeps --noconfirm -f

clean:
	rm -rf locale __pycache__

distclean: clean
	rm -rf dist
