CREATE VIEW WorkerHeartbeats AS
SELECT WorkerName, Host, ServerPort
FROM Worker;

CREATE PROCEDURE addWorker(wname varchar(255), Host varchar(255), ServerPort int, workerVersion varchar(255), reservables varchar(255)[])
LANGUAGE plpgsql
AS
$$
BEGIN
    IF wname IN (SELECT WorkerName FROM Worker) THEN
        RAISE EXCEPTION 'Worker already exists';
    END IF;

    INSERT INTO Worker
    (WorkerName, Host, ServerPort, LastHeartbeat, UsbipiceVersion, Reservables, ShuttingDown)
    VALUES(wname, Host, ServerPort, CURRENT_TIMESTAMP, workerVersion, reservables, 'false');
END
$$;

CREATE FUNCTION removeWorker(wname varchar(255))
RETURNS TABLE (
    "NotificationUrl" varchar(255),
    "SerialId" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    IF wname NOT IN (SELECT WorkerName FROM Worker) THEN
        RAISE EXCEPTION 'Worker does not exist';
    END IF;

    RETURN QUERY SELECT NotificationUrl, Device
    FROM Reservations
    INNER JOIN Device on Reservations.Device = Device.SerialId
    WHERE Device.Worker = wname;

    DELETE FROM Worker
    WHERE WorkerName = wname;
END
$$;

CREATE PROCEDURE heartbeatWorker(wname varchar(255))
LANGUAGE plpgsql
AS
$$
BEGIN
    IF wname NOT IN (SELECT WorkerName FROM Worker) THEN
        RAISE EXCEPTION 'Worker does not exist';
    END IF;

    UPDATE Worker
    SET LastHeartbeat = CURRENT_TIMESTAMP
    WHERE WorkerName = wname ;
END
$$;

CREATE FUNCTION handleWorkerTimeouts(s int)
RETURNS TABLE (
    "SerialId" varchar(255),
    "ClientName" varchar(255),
    "WorkerName" varchar(255)
)
LANGUAGE plpgsql
AS
$$
DECLARE t timestamp;
BEGIN
    t := CURRENT_TIMESTAMP - s * interval '1 second';
    RETURN QUERY
    SELECT Device.SerialId, Reservations.ClientName, Worker.WorkerName
    FROM Worker
    INNER JOIN Device ON Worker.WorkerName = Device.Worker
    INNER JOIN Reservations ON Reservations.Device = Device.SerialId
    WHERE LastHeartbeat < t;

    DELETE FROM Worker
    WHERE LastHeartbeat < t;
END
$$;