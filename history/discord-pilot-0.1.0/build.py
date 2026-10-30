#!/usr/bin/env python3
"""Validate and package the Discord-only native Athena configuration pilot."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
MODULE = ROOT / "module"
NAME = "sys_custom_clear_appfilter_list.xml"
TARGET = Path("system/my_product/etc/extension") / NAME
STOCK_HASH = "15e07bcaf96e0f63456e0b80dd74509fc53acd5362ceece12f0540210cc1018b"


def semantic(element):
    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        (element.text or "").strip(),
        tuple(semantic(child) for child in element),
    )


def main():
    stock = (MODULE / "stock" / NAME).read_bytes()
    if sha256(stock).hexdigest() != STOCK_HASH:
        raise SystemExit("Unexpected stock XML checksum; review the firmware first.")
    original = ET.fromstring(stock)
    if original.findtext("version") != "2025112101":
        raise SystemExit("Unexpected stock version.")
    if original.findtext("filter-name") != "sys_custom_clear_appfilter_list":
        raise SystemExit("Unexpected filter name.")
    if any(node.get("pkg") == "com.discord" for node in original.iter()):
        raise SystemExit("Stock already defines Discord; merge requires review.")

    text = stock.decode("utf-8")
    text, versions = re.subn(r"<version>2025112101</version>", "<version>2025112102</version>", text)
    newline = "\r\n" if "\r\n" in text else "\n"
    text, closes = re.subn(
        r"</filter-conf>",
        '    <p_cond_wl pkg="com.discord" use_kill="true" />' + newline + "</filter-conf>",
        text,
    )
    if versions != 1 or closes != 1:
        raise SystemExit("Stock XML structure does not match the reviewed input.")
    payload = text.encode("utf-8")
    patched = ET.fromstring(payload)
    discord = [node for node in patched if node.get("pkg") == "com.discord"]
    if len(discord) != 1 or discord[0].tag != "p_cond_wl" or discord[0].attrib != {"pkg": "com.discord", "use_kill": "true"}:
        raise SystemExit("Discord entry is not the intended narrow exception.")
    restored = deepcopy(patched)
    restored.remove(next(node for node in restored if node.get("pkg") == "com.discord"))
    restored.find("version").text = "2025112101"
    if semantic(restored) != semantic(original):
        raise SystemExit("Payload changes unrelated stock configuration.")

    target = MODULE / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    (MODULE / "payload.sha256").write_text(sha256(payload).hexdigest() + "\n")
    for script in MODULE.glob("*.sh"):
        subprocess.run(["sh", "-n", str(script)], check=True)

    files = sorted(path for path in MODULE.rglob("*") if path.is_file())
    allowed = {"module.prop", "common.sh", "customize.sh", "post-fs-data.sh", "action.sh", "payload.sha256", "stock/" + NAME, TARGET.as_posix()}
    if {path.relative_to(MODULE).as_posix() for path in files} != allowed:
        raise SystemExit("Unexpected module files.")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / "discord-athena-usekill-0.1.0.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(MODULE).as_posix(), (2026, 10, 29, 0, 0, 0))
            mode = 0o755 if path.name in {"action.sh", "post-fs-data.sh"} else 0o644
            info.create_system = 3
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != allowed:
            raise SystemExit("ZIP validation failed.")
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(f"Validated: exact stock checksum, preserved XML, Discord-only entry, shell syntax, ZIP contents/CRC.\nBuilt: {output}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
