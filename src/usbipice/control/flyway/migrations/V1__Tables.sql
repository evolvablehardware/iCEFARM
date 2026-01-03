CREATE TABLE Worker (
    WorkerName varchar(255) PRIMARY KEY,
    Host varchar(255) NOT NULL,
    ServerPort int NOT NULL,
    LastHeartbeat timestamp NOT NULL,
    UsbipiceVersion varchar(255) NOT NULL,
    Reservables varchar(255)[] NOT NULL,
    ShuttingDown bool NOT NULL
);

CREATE TYPE DeviceState
AS
ENUM('available', 'reserved', 'await_flash_default', 'flashing_default', 'testing', 'broken');

CREATE TABLE Device (
    SerialId varchar(255) PRIMARY KEY NOT NULL,
    Worker varchar(255) REFERENCES Worker(WorkerName) ON DELETE CASCADE NOT NULL,
    DeviceStatus DeviceState NOT NULL
);

CREATE TABLE Reservations (
    Device varchar(255) PRIMARY KEY REFERENCES Device(SerialId) ON DELETE CASCADE,
    ClientName varchar(255) NOT NULL,
    Until timestamp NOT NULL
)
