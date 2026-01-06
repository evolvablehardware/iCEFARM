CREATE PROCEDURE add_device(did varchar(255), wid varchar(255))
LANGUAGE plpgsql AS $$ BEGIN
    IF wid NOT IN (
        SELECT id
        FROM worker
    ) THEN RAISE EXCEPTION 'Worker id does not exist';
    END IF;

    IF did IN (
        SELECT id
        FROM device
    ) THEN RAISE EXCEPTION 'Device serial already exists';
    END IF;

    INSERT INTO device(id, worker_id, device_status)
    VALUES(did, wid, 'await_flash_default');
END $$;

CREATE PROCEDURE update_device_status(did varchar(255), dstate devicestatus)
LANGUAGE plpgsql AS $$ BEGIN
    IF did NOT IN (
        SELECT id
        FROM device
    ) THEN RAISE EXCEPTION 'Device serial does not exist';
    END IF;

    UPDATE device
    SET device_status = dstate
    WHERE id = did;
END $$;

CREATE FUNCTION get_device_worker(device_id varchar(255))
RETURNS TABLE (
    worker_host varchar(255),
    worker_port int
)
LANGUAGE plpgsql AS $$ BEGIN
    IF device_id NOT IN (
        SELECT id
        FROM device
    ) THEN RAISE EXCEPTION 'Device id does not exist';
    END IF;

    RETURN QUERY
    SELECT worker.host,
        worker.port
    FROM device
        INNER JOIN worker ON device.worker_id = worker.id
    WHERE device.id = device_id;
END $$;