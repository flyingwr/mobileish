"""
    This script extracts Android apps and detects typical indicators of Flutter framework usage

    It looks for the shared libraries of Flutter (libapp and libflutter)
    Once done, it will output if they were found or not

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

FLUTTER_ENGINE_ENTRIES = ("Lio/flutter/embedding/engine/FlutterJNI;->startInitialization",
                          "Lio/flutter/embedding/engine/FlutterJNI;->ensureInitializationComplete",
                          "Lio/flutter/embedding/engine/FlutterJNI;->ensureAttachedToNative",
                          "Lio/flutter/embedding/engine/FlutterJNI;->ensureRunningOnMainThread()"
                          "Lio/flutter/embedding/android",
                          "Lio/flutter/embedding/engine")
FLUTTER_LIB_ENTRIES = ("libapp.so", "libflutter.so")

VERIFY_ENGINE_ARGS = ("--verify-engine", "-ve") # lazy argparse

def find_flutter_embedding(path: str) -> Tuple[str, str]:
    with fileinput.input(glob.glob(f"{path}/**/*.smali", recursive=True)) as f:
        for line in f:
            for entry in FLUTTER_ENGINE_ENTRIES:
                if entry in line:
                    return (entry, f.filename())

def main():
    while not (apk_path := input("Enter the APK path: ")) and apk_path.endswith(".apk"):
        continue
    apk_name = os.path.basename(apk_path)

    with zipfile.ZipFile(apk_path) as zip_file:
        shared_libs = {
            entry for entry in FLUTTER_LIB_ENTRIES for name in zip_file.namelist() if name.endswith(entry)
        }

    if "libflutter.so" in shared_libs:
        if "libapp.so" in shared_libs:
            print(f"[+] APK {apk_name} is built with Flutter")
        else:
            print(f"[+] libflutter found in APK {apk_name} but libapp is missing. "
                  "This means the app might not use Flutter although "
                  "it has libflutter included")
            
        try:
            # verify Flutter engine
            if len(sys.argv) > 1 and sys.argv[1] in VERIFY_ENGINE_ARGS:
                print("[ ] Verifying Flutter engine...")

                subprocess.call(f"{dex2smali_path} -o {smali_path} {apk_path}", shell=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                if (result := find_flutter_embedding(smali_path)) is not None:
                    entry, smali_file = result
                    print(f"[+] APK {apk_name} has Flutter engine embedded. "
                          f"Occurrence in Smali code: [{smali_file}:{entry}]")
        finally:
            shutil.rmtree(smali_path, ignore_errors=True)
        return
    
    print(f"[x] APK {apk_name} is not built with Flutter")

if __name__ == "__main__":
    main()