CREATE FUNCTION makeReservations(amount int, notificationUrl varchar(255), clientName varchar(255))
RETURNS TABLE (
    "SerialID" varchar(255),
    "Host" inet,
    "UsbipPort" int,
    "UsbipBus" varchar(255)
)
LANGUAGE plpgsql
AS
$$
BEGIN
    CREATE TEMPORARY TABLE res (
        "SerialID" varchar(255),
        "Host" inet,
        "UsbipPort" int,
        "UsbipBus" varchar(255)
    ) ON COMMIT DROP;

    INSERT INTO res("SerialID", "Host", "UsbipPort", "UsbipBus")
    SELECT Device.SerialID, Host, UsbipPort, UsbipBus 
    FROM Device
    INNER JOIN Worker ON Worker.WorkerName = Device.Worker
    WHERE DeviceStatus = 'available'
    LIMIT amount;

    UPDATE Device
    SET DeviceStatus = 'reserved'
    WHERE Device.SerialID IN (SELECT res."SerialID" FROM res);

    INSERT INTO Reservations(Device, ClientName, Until, NotificationUrl)
    SELECT res."SerialID", clientName, CURRENT_TIMESTAMP + interval '1 hour', notificationUrl
    FROM res;

    RETURN QUERY SELECT * FROM res;
END
$$;

-- CREATE PROCEDURE extendReservations
-- CREATE PROCEDURE endReservations
-- CREATE FUNCTION getReservationTimeouts