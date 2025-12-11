## Database setup

### Postgres
Install postgres:
```
sudo apt install postgresql
```
Start postgres:
```
service postgresql@{version}-main start
```
Create a database and user:
```
sudo -u postgres psql

postgres=# CREATE ROLE {username} LOGIN PASSWORD '{password}';
postgres=# CREATE DATABASE {database} WITH OWNER = {username};
postgres=# GRANT ALL ON SCHEMA public TO {username}; #needed for flyway
```
In order to connect to the database with the new user, authentication must first be configured. This can by done by modifying /etc/postgresql/{version}/main/pg_hba.conf. For local use, the following entry can be added:
```
local {database name} {username} md5
```
Note that docker containers do not use local connections. If adding an entry for a non local connection, make sure to also update postgresql.conf to listen for non local connections. After modifying the configuration, the service needs to be restarted for the changes to apply:
```
service postgresql@{version}-main restart
```
Confirm login works:
```
psql -U {username} {database name}
```

### Flyway
Ensure a java runtime is installed, then install [Flyway](https://documentation.red-gate.com/fd/command-line-277579359.html). Once flyway is installed, create flyway-{version}/conf/flyway.toml and add authentication details. You can use flyway-{version}/conf/flyway.toml.example as a reference. Afterwards, include flyway.locations=["filesystem:migrations"].
```
[flyway]
locations = ["filesystem:migrations"]
cleanDisabled = false # optional
[environments.default]
url = "jdbc:postgresql://localhost:5432/{username}"
user = ""
password = ""
```
*cleanDisabled* allows the use of ```flyway clean```, which drops everything in the database. This is convenient when testing. Run migrations:
```
cd src/usbipice/control/flyway && flyway migrate
```

Flyway ships with its own java runtime, which may be compiled for the wrong architecture. If you encounter an exec format error, ensure you have a java runtime installed and delete the flyway-{version}/jre/bin/java file.

## Control setup
Install usbipice:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set USBIPICE_DATABASE to the [psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING) for the database. Example for running locally:
```
export USBIPICE_DATABASE='dbname={database name} user={username} password={password}'
```
Set USBIPICE_CONTROL_SERVER to the url of the control server. By default, it runs on 8080:
```
export CONTROL_SERVER_URL=http://localhost:8080
```

Run control process:
```
control
```
Run heartbeat process:
```
heartbeat
```

## Control Configuration
| Environment Variable | Description | Default |
|----------------------|-------------|---------|
|USBIPICE_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|USBIPICE_CONTROL_PORT| Port to run on| 8080 |

## Heartbeat Configuration
| Environment Variable | Description | Default |
|----------------------|-------------|---------|
|USBIPICE_DATABASE|[psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)| required |
|USBIPICE_CONTROL_SERVER| Url of control API server | required |
|USBIPICE_HEARTBEAT_SECONDS| Duration between worker heartbeats | 15 |
|USBIPICE_TIMEOUT_DURATION_SECONDS | Maximum time a worker can go without responding to a heartbeat before being removed | 60 |
|USBIPICE_TIMEOUT_POLL_SECONDS| Duration between checks for whether a worker has timed out | 15|
|USBIPICE_RESERVATION_POLL_SECONDS | Duration between checks for ended reservations | 30|
|USBIPICE_RESERVATION_EXPIRING_NOTIFY_AT_MINUTES| Amount of time left when clients should be notified that their device reservation is expiring soon | 20
|USBIPICE_RESERVATION_EXPIRING_NOTIFICATION_SECONDS| Frequency to check for and send reservation ending soon notifications | 300