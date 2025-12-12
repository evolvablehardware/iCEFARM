CREATE FUNCTION makeReservations(amount int, clientName varchar(255))
RETURNS TABLE (
    "SerialID" varchar(255),
    "Host" inet,
    "WorkerPort" int
)
LANGUAGE plpgsql
AS
$$
BEGIN
    CREATE TEMPORARY TABLE res (
        "SerialID" varchar(255),
        "Host" inet,
        "WorkerPort" int
    ) ON COMMIT DROP;

    INSERT INTO res("SerialID", "Host", "WorkerPort")
    SELECT Device.SerialID, Host, Worker.ServerPort
    FROM Device
    INNER JOIN Worker ON Worker.WorkerName = Device.Worker
    WHERE DeviceStatus = 'available'
    LIMIT amount;

    UPDATE Device
    SET DeviceStatus = 'reserved'
    WHERE Device.SerialID IN (SELECT res."SerialID" FROM res);

    INSERT INTO Reservations(Device, ClientName, Until)
    SELECT res."SerialID", clientName, CURRENT_TIMESTAMP + interval '1 hour'
    FROM res;

    RETURN QUERY SELECT * FROM res;
END
$$;

CREATE FUNCTION extendReservations(client_name varchar(255), serial_ids varchar(255)[])
RETURNS TABLE (
    "Device" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN QUERY
    UPDATE Reservations
    SET Until = CURRENT_TIMESTAMP + interval '1 hour'
    WHERE Device = ANY(serial_ids)
    AND ClientName = client_name
    RETURNING Device;
END
$$;

CREATE FUNCTION extendAllReservations(client_name varchar(255))
RETURNS TABLE (
    "Device" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN QUERY
    UPDATE Reservations
    SET Until = CURRENT_TIMESTAMP + interval '1 hour'
    WHERE ClientName = client_name
    RETURNING Device;
END
$$;

CREATE FUNCTION endReservations(client_name varchar(255), serial_ids varchar(255)[])
RETURNS TABLE (
    "Device" varchar(255),
    "WorkerIp" inet,
    "WorkerServerPort" int
)
LANGUAGE plpgsql
AS 
$$
BEGIN
    CREATE TEMPORARY TABLE res (
        "Device" varchar(255),
        "WorkerIp" inet,
        "WorkerServerPort" int
    ) ON COMMIT DROP;

    INSERT INTO res("Device")
    SELECT Device
    FROM Reservations
    WHERE ClientName = client_name
    AND Device = ANY(serial_ids);

    RETURN QUERY
    SELECT res."Device", Worker.Host, Worker.ServerPort
    FROM res
    INNER JOIN Reservations ON res."Device" = Reservations.Device
    INNER JOIN Device ON res."Device" = Device.SerialID
    INNER JOIN Worker ON Device.Worker = Worker.WorkerName;

    DELETE FROM Reservations
    WHERE Device IN (SELECT res."Device" FROM res);

    UPDATE Device
    SET DeviceStatus = 'await_flash_default'
    WHERE Device.SerialID IN (SELECT res."Device" FROM res);
END
$$;

CREATE FUNCTION endAllReservations(client_name varchar(255))
RETURNS TABLE (
    "Device" varchar(255),
    "WorkerIp" inet,
    "WorkerServerPort" int
)
LANGUAGE plpgsql
AS 
$$
BEGIN
    CREATE TEMPORARY TABLE res (
        "Device" varchar(255)
    ) ON COMMIT DROP;

    INSERT INTO res("Device")
    SELECT Device
    FROM Reservations
    WHERE ClientName = client_name;

    RETURN QUERY
    SELECT res."Device", Worker.Host, Worker.ServerPort
    FROM res
    INNER JOIN Reservations ON res."Device" = Reservations.Device
    INNER JOIN Device ON res."Device" = Device.SerialID
    INNER JOIN Worker ON Device.Worker = Worker.WorkerName;

    DELETE FROM Reservations
    WHERE Device IN (SELECT res."Device" FROM res);

    UPDATE Device
    SET DeviceStatus = 'await_flash_default'
    WHERE Device.SerialID IN (SELECT res."Device" FROM res);
END
$$;

CREATE FUNCTION handleReservationTimeouts()
RETURNS TABLE (
    "Device" varchar(255),
    "ClientName" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    CREATE TEMPORARY TABLE res (
        "Device" varchar(255)
    ) ON COMMIT DROP;

    INSERT INTO res("Device")
    SELECT Device
    FROM Reservations
    WHERE Until < CURRENT_TIMESTAMP;

    RETURN QUERY 
    SELECT res."Device", Reservations.ClientName
    FROM res
    INNER JOIN Reservations ON res."Device" = Reservations.Device;

    DELETE FROM Reservations
    WHERE Device IN (SELECT res."Device" FROM res);

    UPDATE Device
    SET DeviceStatus = 'await_flash_default'
    WHERE Device.SerialID IN (SELECT res."Device" FROM res);
END
$$;

CREATE FUNCTION getReservationsEndingSoon(mins int)
RETURNS TABLE (
    "Device" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN QUERY
    SELECT Reservations.Device
    FROM Reservations
    WHERE Reservations.Until < CURRENT_TIMESTAMP + interval '1 minute' * mins;
END
$$;

CREATE FUNCTION getDeviceCallBack(client_id varchar(255))
RETURNS TABLE (
    "ClientId" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    IF deviceserial NOT IN (SELECT SerialId FROM Device) THEN
        RAISE EXCEPTION 'SerialID does not exist';
    END IF;

    RETURN QUERY SELECT ClientName FROM Reservations
    WHERE Device = deviceserial;
END
$$;

CREATE FUNCTION getDeviceWorker(deviceserial varchar(255))
RETURNS TABLE (
    "Host" inet,
    "Serverport" int
)
LANGUAGE plpgsql
AS
$$
BEGIN
    IF deviceserial NOT IN (SELECT SerialId FROM Device) THEN
        RAISE EXCEPTION 'SerialID does not exist';
    END IF;

    RETURN QUERY SELECT Worker.Host, Worker.ServerPort
    FROM Device
    INNER JOIN Worker ON Device.Worker = Worker.WorkerName
    WHERE Device.SerialId = deviceserial;
END
$$;
