# Concrete command line examples for setting up the database for icefarm control server and client

username = "icefarm_user"
password = "icefarm_pass"
database = "icefarm_db"
worker_config="src/usbipice/worker/config_alpha.ini"
worker_name="worker_alpha"
USBIPICE_DATABASE=f"dbname={database} user={username} password={password}"
command = f"sudo -u postgres psql \n CREATE ROLE {username} LOGIN PASSWORD '{password}'; \n CREATE DATABASE {database} WITH OWNER = {username}; \n GRANT ALL ON SCHEMA public TO {username}; #needed for flyway\n"


print("=========================== Database Setup ===========================\n")
print(command)
print("======================================================================")

#Control Server
print(f"""=========================== Control Server ===========================

source .venv/bin/activate
export USBIPICE_DATABASE='dbname={database} user={username} password={password}'
export  USBIPICE_CONTROL_SERVER=http://localhost:8080
control

======================================================================""")

#Heartbeat server
print("========================== Heartbeat Server ==========================")
print(f"""

source .venv/bin/activate
export USBIPICE_DATABASE='dbname={database} user={username} password={password}'
export  USBIPICE_CONTROL_SERVER=http://localhost:8080
heartbeat

========================================================================""")


#Worker Server
print("======================== Worker Server (local) =========================")
print(f"""
source .venv/bin/activate
export USBIPICE_DATABASE='dbname={database} user={username} password={password}'
export USBIPICE_CONTROL_SERVER=http://localhost:8080
.venv/bin/worker -c {worker_config}
sudo USBIPICE_DATABASE="{USBIPICE_DATABASE}"  .venv/bin/worker -c {worker_config}

======================================================================""")

#Worker Server
print("======================== Worker Server (docker) ========================")
print(f"""
Worker Docker
export USBIPICE_DATABASE='dbname={database} user={username} password={password}'
export  USBIPICE_CONTROL_SERVER=http://localhost:8080
docker run --privileged -v /dev:/dev -v /lib/modules:/lib/modules -v /run/udev:/run/udev \
  -v /tmp:/tmp -d --network=host -e USBIPICE_DATABASE="$USBIPICE_DATABASE" \
  -e USBIPICE_WORKER_NAME="{worker_name}" -e USBIPICE_CONTROL_SERVER="$USBIPICE_CONTROL_SERVER" \
  /src/usbipice/worker/deploy/noble-generic.dockerfile .venv/bin/worker -c {worker_config}

=====================================================================""")

#Example Client
print("=========================== Example Client ==========================")
print(f"""
source .venv/bin/activate
export  USBIPICE_CONTROL_SERVER=http://localhost:8080
python3 examples/pulse_count_driver/main.py
=====================================================================
""")

