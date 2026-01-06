CREATE TABLE worker (
    id              varchar(255)    PRIMARY KEY,
    host            varchar(255)    NOT NULL,
    port            int             NOT NULL,
    heartbeat       timestamp       NOT NULL,
    farm_version    varchar(255)    NOT NULL,
    reservables     varchar(255)[]  NOT NULL,
    shutting_down   bool            NOT NULL
);

CREATE TYPE devicestatus
AS
ENUM('available', 'reserved', 'await_flash_default', 'flashing_default', 'testing', 'broken');

CREATE TABLE device (
    id              varchar(255)    PRIMARY KEY NOT NULL,
    worker_id       varchar(255)    REFERENCES worker(name) ON DELETE CASCADE NOT NULL,
    device_status   devicestatus    NOT NULL
);

CREATE TABLE reservations (
    device_id       varchar(255)    PRIMARY KEY REFERENCES device(id) ON DELETE CASCADE,
    client_id       varchar(255)    NOT NULL,
    until           timestamp       NOT NULL
);

CREATE OR REPLACE VIEW device_reservations
SELECT device.id, device.worker_id, device.device_status, reservations.client_id
FROM device
LEFT JOIN reservations ON reservations.device = device.id;
