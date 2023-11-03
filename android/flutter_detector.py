"""
    This script extracts Android apps and detects typical indicators of Flutter framework usage

    It looks for the shared libraries of Flutter (libapp and libflutter)
    Once done, it will output if they were found or not with the addition of
    some information about Dart SDK discovered with the libraries

    If argument --verify-engine/-ve is passed, the script will also check if
    Flutter engine is embedded in the app. This will avoid false positives
    like when the app has Flutter libraries but load none of them

    Java is required to run dex2smali (will happen if the mentioned argument is passed)
"""
from typing import Tuple

import fileinput
import glob
import os
import shutil
import subprocess
import sys
import zipfile

# https://github.com/pxb1988/dex2jar/releases/download/v2.4/dex-tools-v2.4.zip
dex2smali_path = r"dex-tools-v2.4\d2j-dex2smali.bat"
smali_path = "smali"

snapshot_list_url = "https://gist.github.com/nfalliere/84803aef37291ce225e3549f3773681b/raw"

DART_SNAPSHOT_MAGIC_NUM = b"\xf5\xf5\xdc\xdc"

FLUTTER_ENGINE_ENTRIES = ("Lio/flutter/embedding/engine/FlutterJNI;->startInitialization",
                          "Lio/flutter/embedding/engine/FlutterJNI;->ensureInitializationComplete",
                          "Lio/flutter/embedding/engine/FlutterJNI;->ensureAttachedToNative",
                          "Lio/flutter/embedding/engine/FlutterJNI;->ensureRunningOnMainThread")
FLUTTER_LIB_ENTRIES = ("libapp.so", "libflutter.so")

VERIFY_ENGINE_ARGS = ("--verify-engine", "-ve") # lazy argparse

def find_flutter_embedding(smali_path: str) -> (Tuple[str, str] | None):
    with fileinput.input(glob.glob(f"{smali_path}/**/*.smali", recursive=True)) as f:
        for line in f:
            for entry in FLUTTER_ENGINE_ENTRIES:
                if entry in line:
                    return (entry, f.filename())
    return None
                
def get_snapshot_hash(libapp_content: bytes) -> (str | None):
    if (offset := libapp_content.find(DART_SNAPSHOT_MAGIC_NUM)) == -1:
        return None
    return libapp_content[offset + 20:offset + 52].decode()

def get_dart_version(libflutter_content: bytes) -> (str | None):
    if (end_offset := libflutter_content.find(b"(stable)")) == -1:
        return None
    offset = libflutter_content.rfind(b"\x00", 0, end_offset) + 1
    return libflutter_content[offset:end_offset].strip().decode()

def main():
    while not (apk_path := input("Enter the APK path: ")) and apk_path.endswith(".apk"):
        continue
    apk_name = os.path.basename(apk_path)

    dart_version, snapshot_hash = None, None

    with zipfile.ZipFile(apk_path) as zip_file:
        flutter_libs_found = set()

        libs = [name for name in zip_file.namelist() if name.startswith("lib/")]
        for lib in libs:
            if (lib_name := os.path.basename(lib)) in FLUTTER_LIB_ENTRIES:
                flutter_libs_found.add(lib_name)

                lib_content = zip_file.read(lib)

            if lib_name == "libapp.so":
                snapshot_hash = get_snapshot_hash(lib_content)
            # getting the snapshot version hash might not be enough to know the Dart version of some apps
            # some snapshot hashes are used repeatedly in different releases of Dart. example:
            # snapshot hash `90b56a561f70cd55e972cb49b79b3d8b` is the same from Dart 3.0.3 to 3.0.7
            # a list of Dart versions can be found here: https://gist.github.com/nfalliere/84803aef37291ce225e3549f3773681b
            elif lib_name == "libflutter.so":
                dart_version = get_dart_version(lib_content)

    if "libflutter.so" in flutter_libs_found:
        if "libapp.so" in flutter_libs_found:
            print(f"[+] APK {apk_name} is built with Flutter")
            if dart_version is not None:
                print(f"[+] Dart SDK version: {dart_version}; snapshot hash: {snapshot_hash}")
        else:
            print(f"[+] libflutter found in APK {apk_name} but libapp is missing. "
                  "This means the app might not use Flutter although it has libflutter included")
            
        try:
            # verify Flutter engine
            if len(sys.argv) > 1 and sys.argv[1] in VERIFY_ENGINE_ARGS:
                print("[+] Verifying Flutter engine...")

                subprocess.call(f"{dex2smali_path} -o {smali_path} {apk_path}", shell=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                if (result := find_flutter_embedding(smali_path)) is not None:
                    entry, smali_file = result
                    print(f"[+] APK {apk_name} has Flutter engine embedded. "
                          f"Occurrence in Smali code: [{smali_file}] {entry}")
        finally:
            shutil.rmtree(smali_path, ignore_errors=True)

        return
    
    print(f"[x] APK {apk_name} is not built with Flutter")

if __name__ == "__main__":
    main()