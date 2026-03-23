# Local Development Setup
**This is only needed if you are modifying iCEFARM specifically and want to use a debugger. The provided images are easier and faster to run, this setup should be avoided if possible.**

## Database Setup
iCEFARM uses postgres. Install postgres:
```
sudo apt install postgresql
```
Start postgres:
```
service postgresql@{version}-main start
```
Create a database and user. Note that this can be configured using the [command generator](./command_generators.py):
```
sudo -u postgres psql
postgres=# CREATE ROLE {username} LOGIN PASSWORD '{password}';
postgres=# CREATE DATABASE {database} WITH OWNER = {username};
postgres=# GRANT ALL ON SCHEMA public TO {username}; #needed for flyway
```
In order to connect to the database with the new user, authentication must first be configured. This can by done by modifying ```/etc/postgresql/{version}/main/pg_hba.conf```. For local use, the following entry can be added:
```
local {database name} {username} md5
```
Note that docker containers do not use local connections. To add an entry for another device:
```
host {database name} {username} {ip}/0 md5
```
For non-local use, postgres needs to be configured to listen for other addresses. This can be done by changing ```listen_addresses``` in ```/etc/postgresql/{version}/main/postgresql.conf```.
Confirm that the login works:
```
psql -U {username} {database name}
```
Now, the database connection string needs to be configured. This is a [libpg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING). This needs to be configured on all machines running the control or worker process:
```
export ICEFARM_DATABASE='host={ip} port=5432 dbname={database name} user={username} password={password}
```
Confirm that the connection string works:
```
psql -d "$ICEFARM_DATABASE"
```
Note that you have to be careful when passing the connection string around, as it may contain spaces.

Flyway is used in order to apply migrations. Start by installing [Flyway](https://documentation.red-gate.com/fd/command-line-277579359.html). Try running flyway:
```
flyway
```
Flyway ships with its own java runtime, which may be compiled for the wrong architecture. If you encounter an exec format error, ensure you have a separate java runtime installed and delete the ```flyway-{version}/jre/bin/java``` file. Now, Flyway needs to be configured. The configuration file is located at ```flyway-{version}/conf/flyway.toml```. An example is provided by Flyway at ```flyway-{version}/conf/flyway.toml```. In addition, here is a configuration that works with the project:
```
[flyway]
locations = ["filesystem:migrations"]
cleanDisabled = false # optional
[environments.default]
url = "jdbc:postgresql://localhost:5432/{database}"
user = ""
password = ""
```
The ```flyway.cleanDisabled``` setting is optional and enables the use of the ```flyway clean``` command. This essentially drops all of the objects in the database and is useful during development. In order to run the migrations:
```
cd src/ICEFARM/control/flyway && flyway migrate
```
This can also be done with the ```database-rebuild``` vscode task. Note that in addition to running the migrations, it also runs clean beforehand.


## Building Firmware
If not already installed, install the [pico-sdk](https://github.com/raspberrypi/pico-sdk) and [pico-ice-sdk](https://github.com/tinyvision-ai-inc/pico-ice-sdk). Make sure to run ```git submodule update --init``` in the pico-ice-sdk repo. Commands:

```
git clone https://github.com/tinyvision-ai-inc/pico-ice-sdk.git
cd pico-ice-sdk
git submodule update --init --recursive
```

```
git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
git submodule update --init --recursive
```

Create symlinks for the sdks in the firmware directory:
```
ln -s [full_path]/pico-sdk pico-sdk
ls -s [full_path]/pico-ice-sdk pico-ice-sdk
```

Run build.sh in this directory, or use the ```build-firmware``` task:
```
cd src/ICEFARM/worker/firmware
chmod +x build.sh
./build.sh
```

## Configuration
For the control server:

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
|ICEFARM_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|ICEFARM_CONTROL_PORT| Port to run on | 8080|

Configuration for the worker can be done using environment variables or a toml file. Environment variables take precedence over the configuration file. Note that ICEFARM_DATABASE is not able to be provided through the configuration file. An example is [provided](./src/ICEFARM/worker/example_config.ini). The worker has to run with sudo in order to upload firmware to devices. This means that the environment variables need to be passed along:
```
sudo ICEFARM_DATABASE="$ICEFARM_DATABASE ICEFARM_WORKER_CONFIG=$ICEFARM_WORKER_CONFIG [command]
```
This may also be done with the -E flag, but this is not supported on all systems.

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| ICEFARM_WORKER_CONFIG | Path to config file | None|
|ICEFARM_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|ICEFARM_WORKER_NAME| Name of the worker for identification purposes. Must be unique.| required|
|ICEFARM_CONTROL_SERVER | Url to control server | required |
|ICEFARM_DEFAULT| Path for Ready state firmware | required |
|ICEFARM_PULSE_COUNT | Path for PulseCount state firmware | required |
|ICEFARM_WORKER_LOGS | Log location | None - required if running with uvicorn|
|ICEFARM_SERVER_PORT| Port to host server on | 8081|
|ICEFARM_VIRTUAL_IP| Ip for clients to reach worker with | First result from hostname -I |
|ICEFARM_VIRTUAL_PORT| Port for clients to reach worker with | 8081 |

## Preparing Devices
The picos need to be plugged into the worker and running firmware that has tinyusb loaded. The [rp2_hello_world](https://github.com/tinyvision-ai-inc/pico-ice-sdk/tree/main/examples/rp2_hello_world) example from the pico-ice-sdk works for this purpose.

## Installing Module
Install iCEFARM module:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

#### Debugging
Debug configurations are available in the [launch.json](./.vscode/launch.json). The worker requires sudo in order to upload firmware to the devices. Note that sudo changes the environment variables, so it is recommended to use a configuration file.
```
sudo ICEFARM_DATABASE="$ICEFARM_DATABASE" ICEFARM_WORKER_CONFIG="$ICEFARM_WORKER_CONFIG" .venv/bin/worker
```

#### Uvicorn
iCEFARM normally runs using uvicorn but can also use the flask debug server. There's not really a reason to run uvicorn in a development environment, as it does not allow for debugging, but otherwise should run identically. This mostly here for the sake of documenting how iCEFARM is started inside containers.

Uvicorn does not access environment variables unless they are contain a special prefix, which is not included in the iCEFARM environment variables. Variables can be passed with a [.env](https://github.com/theskumar/python-dotenv) file instead. The provided ```.uvicorn_env_bridge``` file passes iCEFARM related environment variables to uvicorn. As a result, configuration can be done through environment variables normally provided this environment file is included.
Control:
```
uvicorn ICEFARM.control.app:run_uvicorn --env-file .uvicorn_env_bridge --factory --host 0.0.0.0 --port 8080
```
Worker:
```
sudo ICEFARM_DATABASE="$ICEFARM_DATABASE" ICEFARM_WORKER_CONFIG=$ICEFARM_WORKER_CONFIG .venv/bin/uvicorn ICEFARM.worker.app:run_uvicorn --env-file .uvicorn_env_bridge --factory --host 0.0.0.0 --port 8081
```
### Workflow
Vscode debug configurations are available for both the worker and control. There is also an assortment of vscode tasks. The task ```database-clear``` removes workers from the database and is useful to fix invalid worker/device states (this also causes all reservations/devices to be removed). This can also be done with ```psql -d "$ICEFARM_DATABASE" -c 'delete from worker;```.

### Testing
Tests assume that a newly launched worker and control instance are running with at least two devices available. If you do not have two devices, you can use ```worker/test.py```. This applies patches to emulate device behavior without needing physical access. Running tests:
```pytest ./tests --url [control url]```
Note that if you do not specify the test directory, and have pico-sdk symlinks, pytest may pick up additional tests from dependencies. This applies patches to emulate device behavior without needing physical access. Tests are also automatically performed on main/development commits.

