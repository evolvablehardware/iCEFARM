## Database setup

### Postgres
Install 
```sudo apt install postgresql```.
Start a shell with
```sudo -u postgres psql```.
Create database and user:
```
CREATE ROLE {user} LOGIN PASSWORD {pass};
CREATE DATABASE {name} WITH OWNER = {user};
```
Configure remote connections. This can be done by modifying /etc/postgresql/{version}/main/pg_hba.conf. Afterwards, apply the changes with 
```service postgresql@{version}-main.service reload```.

### Flyway
- Install [Flyway](https://documentation.red-gate.com/fd/command-line-277579359.html)
- Create a flyway.toml in /flyway/conf - see /flyway/conf/flyway.toml.example for authentication details. Add flyway.locations=["filesystem:migrations"].
- Run ```flyway migrate```

## Control-server setup
### Pythons deps 
```
pip install -r requirements.txt
```

### Environment Configuration
- USBIPICE_DATABASE to [psycopg connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)

### Run
```
python3 server.py 
python3 heartbeat.py
```
