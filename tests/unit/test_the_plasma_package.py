"""The Plasma wallpaper package (syncrain/plasma/package/): its metadata, its settings and the two
QML files that use them agree. tests/plasma/ runs it."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from syncrain import engine

PACKAGE = "syncrain/plasma/package"


def settings(root):
    xml = ET.parse(root / PACKAGE / "contents/config/main.xml")
    ns = {"k": "http://www.kde.org/standards/kcfg/1.0"}
    return {e.get("name"): (e.get("type"), e.findtext("k:default", default="", namespaces=ns))
            for e in xml.getroot().iterfind(".//k:entry", ns)}


def test_the_metadata_names_a_plasma_6_wallpaper(root):
    meta = json.loads((root / PACKAGE / "metadata.json").read_text(encoding="utf-8"))
    assert meta["KPackageStructure"] == "Plasma/Wallpaper"
    assert meta["KPlugin"]["Id"] == "org.syncrain.wallpaper"
    assert meta["X-Plasma-API-Minimum-Version"].startswith("6.")


def test_every_setting_is_on_the_settings_page_and_used(root):
    entries = settings(root)
    page = (root / PACKAGE / "contents/ui/config.qml").read_text(encoding="utf-8")
    main = (root / PACKAGE / "contents/ui/main.qml").read_text(encoding="utf-8")
    assert set(re.findall(r"property \w+ cfg_(\w+)", page)) == set(entries)
    used = set(re.findall(r"(?:c|root\.configuration)\.(\w+)", main))
    assert used == set(entries)


def test_the_defaults_are_syncrain_s(root):
    entries = settings(root)
    theme = engine.load_meta()["themes"]["nixos"]
    assert entries["Theme"][1] == "nixos" and entries["Channel"][1] == "public" and entries["Fps"][1] == "30"
    assert float(entries["Hieroglyphs"][1]) == theme["rain"]["hieroglyphs"]
    assert entries["Rainbow"][1] == theme["rain"]["rainbow"]
    for key in ("Glow", "Bloom", "BgGain", "Speed", "Density", "Scale"):
        assert float(entries[key][1]) == 1.0, key
    assert entries["Snow"][1] == "true" and entries["PauseUnder"][1] == "maximized"
