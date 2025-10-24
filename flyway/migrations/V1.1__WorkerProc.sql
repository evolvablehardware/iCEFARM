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

CREATE PROCEDURE removeWorker(wname varchar(255))
LANGUAGE plpgsql
AS
$$
BEGIN
    IF wname NOT IN (SELECT WorkerName FROM Worker) THEN
        RAISE EXCEPTION 'Worker does not exist';
    END IF;

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

CREATE FUNCTION getWorkerTimeouts(t timestamp)
RETURNS TABLE (
    "NotificationUrl" varchar(255),
    "SerialId" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN QUERY
    SELECT NotificationUrl, SerialId
    FROM Worker
    INNER JOIN Device ON Worker.WorkerName = Device.Worker
    INNER JOIN Reservations ON Reservations.Device = Device.SerialId
    WHERE LastHeartbeat < t;
    
    DELETE FROM Worker
    WHERE LastHeartbeat < t;
END
$$;