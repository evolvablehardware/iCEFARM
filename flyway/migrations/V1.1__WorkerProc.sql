CREATE VIEW WorkerHeartbeats AS
SELECT WorkerName, Host, ServerPort
FROM Worker;

CREATE PROCEDURE addWorker(wname varchar(255), Host inet, UsbipPort int, ServerPort int)
LANGUAGE plpgsql 
AS
$$
BEGIN
    IF wname IN (SELECT WorkerName FROM Worker) THEN
        RAISE EXCEPTION 'Worker already exists';
    END IF;

    INSERT INTO Worker
    (WorkerName, Host, UsbipPort, ServerPort, LastHeartbeat)
    VALUES(wname, Host, UsbipPort, ServerPort, CURRENT_TIMESTAMP);
END
$$;

-- # TODO
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
    "Worker" varchar(255),
    "NotificationUrl" varchar(255),
    "SerialId" varchar(255)
)
LANGUAGE plpgsql
AS
$$
DECLARE t timestamp;
BEGIN
    t := CURRENT_TIMESTAMP + s * interval '1 second';
    RETURN QUERY
    SELECT Worker, NotificationUrl, SerialId
    FROM Worker
    INNER JOIN Device ON Worker.WorkerName = Device.Worker
    LEFT JOIN Reservations ON Reservations.Device = Device.SerialId
    WHERE LastHeartbeat < t;
    
    DELETE FROM Worker
    WHERE LastHeartbeat < t;
END
$$;