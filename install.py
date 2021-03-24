# !/usr/bin/python3
from pathlib import Path
import os
import platform
import getpass

command_prefix = ""
running_user = getpass.getuser()
if running_user != "root":
    command_prefix = "sudo "

# first get some info for config
input_ical_url = input("your ical-url: ")
if not input_ical_url.startswith("https"):
    raise Exception("Your ical-url must start with 'https://'")

input_hcloud_api = input("your hetzner-cloud-api-key (with r/w access): ")
if input_hcloud_api == "":
    raise Exception("Your api-key is empty")

input_random_token = input("The label 'token' you used to tag your hetzner-ressources: ")

if input_random_token == "":
    raise Exception("Your random-token is empty")

# Write config.py
print("write config.py")

init_config_file = "assets/config.py.default"
target_config_file = "config.py"

init_config_file_content = Path(init_config_file).read_text(encoding="utf-8").replace(
    "%YOUR_API_TOKEN%",input_hcloud_api).replace(
    "%YOUR_IMAGE_TOKEN%", input_random_token ).replace(
    "%YOUR_ICAL_URL%", input_ical_url)

try:
    Path(target_config_file).write_text(data=init_config_file_content)
except:
    raise Exception(target_config_file + " could not be installed")

#  install requirements into venv
if platform.system() in ("Darwin", "Linux"):
    venv_path = os.getcwd() + "/venv/"
    venv_python_path = venv_path + "bin/python"

    cmd_install_requirements = venv_python_path + " -m pip install -r " + os.getcwd() + "/requirements.txt"

    # install venv
    if not Path(venv_path).exists():
        os.system("python3 -m venv " + venv_path)

    # install requirements in venv
    if Path(venv_path).exists():
        os.system(cmd_install_requirements)
    else:
        raise Exception(venv_path + " did not exists. could not install requirements")

if platform.system() == "Linux":

    path_to_systemd = "/etc/systemd/system/"

    init_service_file = "assets/hcloud_calendar_automation.service"

    service_file_content = Path(init_service_file).read_text(encoding="utf-8").replace("%PATH_TO_MAIN%",
                                                                                       os.getcwd()).replace(
        "%PATH_TO_VENV_PYTHON%", venv_python_path)

    service_name = init_service_file.split("/")[1]

    target_service_file = path_to_systemd + service_name

    if Path(path_to_systemd).exists():
        try:
            Path(target_service_file).write_text(data=service_file_content)
        except:
            raise Exception(service_name + " could not be installed")

        os.system(command_prefix + "systemctl daemon-reload")
        os.system(command_prefix + "systemctl enable " + service_name)
        os.system(command_prefix + "systemctl start " + service_name)
    else:
        raise Exception(path_to_systemd + " did not exists. Is systemd installed?")
else:
    print("")
    print("")
    print(
        "this install script did not fully-support your OS (" + platform.system() + "), because we are missing systemd.")
    print("Please install it manually.")
    print("all requirements and your config should have been installed correctly")
    print("")
    print("you can start manually: " + venv_python_path + " " + os.getcwd() + "/main.py")
