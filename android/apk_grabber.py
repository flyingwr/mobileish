"""
    In order to run this script, there must be and Android device attached to ADB

    This script will not work with multiple devices attached
    To do so, there should be implemented some algorithm to specify the attached device

    Java is required to run APKEditor if some app has split APKs

    The package name should be the ID of the app
    Example of package name (Oxy Proxy app): io.oxylabs.proxymanager
"""

import os
import shutil
import subprocess

# https://github.com/REAndroid/APKEditor/releases/download/V1.3.2/APKEditor-1.3.2.jar
apk_editor_path = "tools/APKEditor-1.3.2.jar"
temp_path = "temp"

def main():
    while not (target_package := input("Enter the package name: ")):
        continue

    try:
        output = subprocess.check_output(f"adb shell pm path {target_package}")
        lines = output.splitlines()
    except subprocess.CalledProcessError:
        print("[-] Target app not found")
        return

    has_multiple = len(lines) > 1

    if os.path.isdir(temp_path):
        for file in os.listdir(temp_path):
            os.remove(file)
    elif has_multiple:
        os.mkdir(temp_path)

    for path in lines:
        path = path.decode().replace("package:", "")

        apk_name = path.rsplit("/", 1)[-1]
        print(f"[+] Copying APK {apk_name}...")

        output = f"{temp_path}/{apk_name}" if has_multiple else f"{target_package}.apk"
        subprocess.call(f"adb pull {path} {output}", stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    if has_multiple:
        print(f"[+] Joining multiple APKs found for package {target_package}")

        subprocess.call(f"java -jar {apk_editor_path} m -i {temp_path} -o {target_package}.apk -f",
                        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        shutil.rmtree(temp_path)

if __name__ == "__main__":
    main()