import subprocess
import os

# NOTE: this is just for testing and should not be used

SSH_HOSTS = os.environ.get("USBIPICE_HOSTS")

if SSH_HOSTS:
    SSH_HOSTS = list(SSH_HOSTS.split(","))

IMAGE_REPO = os.environ.get("DOCKER_IMAGE_REPO")
USBIPICE_DATABASE = os.environ.get("USBIPICE_DATABASE")
if not IMAGE_REPO or not USBIPICE_DATABASE or not SSH_HOSTS:
    raise Exception("Configuration error")

hoststr = ",".join(SSH_HOSTS)

# verify we can connect
subprocess.run(["pdsh", "-w", hoststr, "echo", "test"], check=True)

# NOTE: we remove ALL containers here
subprocess.run(["pdsh", "-w", hoststr, "eval", "docker stop $(docker ps -a -q)"])
subprocess.run(["pdsh", "-w", hoststr, "eval", "docker rm $(docker ps -a -q)"])

subprocess.run(["pdsh", "-w", hoststr, "docker", "pull", IMAGE_REPO])

for host in SSH_HOSTS:
    subprocess.run(["pdsh", "-w", host, "docker", "run",
                    "--privileged",
                    "-v", "/dev:/dev",
                    "-v", "/lib/modules:/lib/modules",
                    "-v", "/tmp:/tmp",
                    "-v", "/run/udev:/run/udev:ro",
                    "--network=host",

                    "-d",

                    "-e",
                    f"USBIPICE_DATABASE='{USBIPICE_DATABASE}'",
                    "-e",
                    f"USBIPICE_WORKER_NAME='{host}'",

                    IMAGE_REPO,
                    ".venv/bin/worker",
                    "-c",
                    "src/usbipice/worker/example_config.ini"])
