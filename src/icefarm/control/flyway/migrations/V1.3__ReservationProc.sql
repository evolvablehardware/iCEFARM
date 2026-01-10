CREATE FUNCTION make_reservations (
    amount int,
    client_name varchar(255),
    reservation_type varchar(255)
) RETURNS TABLE (
    device_id varchar(255),
    worker_host varchar(255),
    worker_port int
) LANGUAGE plpgsql AS $$
    BEGIN CREATE TEMPORARY TABLE res (
        device_id varchar(255),
        worker_host varchar(255),
        worker_port int
    ) ON COMMIT DROP;

    INSERT INTO res(device_id, worker_host, worker_port)
    SELECT device.id,
        worker.host,
        worker.port
    FROM device
        INNER JOIN worker ON worker.id = device.worker_id
    WHERE device_status = 'available'
        AND reservation_type = ANY(worker.reservables)
        AND NOT worker.shutting_down
    LIMIT amount;

    UPDATE device
    SET device_status = 'reserved'
    WHERE device.id IN (
            SELECT res.device_id
            FROM res
        );

    INSERT INTO reservations(device_id, client_id, until)
    SELECT res.device_id,
        client_name,
        CURRENT_TIMESTAMP + interval '1 hour'
    FROM res;

    RETURN QUERY
    SELECT *
    FROM res;
END $$;

CREATE FUNCTION has_reservations(wid varchar(255))
RETURNS bool
LANGUAGE plpgsql AS $$ BEGIN
    RETURN EXISTS (
        SELECT *
        FROM reservations
            INNER JOIN device ON reservations.device_id = device.id
            INNER JOIN worker ON worker.id = device.worker_id
    );
END $$;

CREATE FUNCTION extend_reservations(
    client_name varchar(255),
    serial_ids varchar(255) []
)
RETURNS TABLE (
    device_id varchar(255)
)
LANGUAGE plpgsql AS $$ BEGIN
    RETURN QUERY
    UPDATE reservations
    SET until = CURRENT_TIMESTAMP + interval '1 hour'
    WHERE reservations.device_id = ANY(serial_ids)
        AND client_id = client_name
    RETURNING reservations.device_id;
END $$;

CREATE FUNCTION extend_all_reservations(client_name varchar(255))
RETURNS TABLE (
    device_id varchar(255)
    )
LANGUAGE plpgsql AS $$ BEGIN
    RETURN QUERY
    UPDATE reservations
    SET until = CURRENT_TIMESTAMP + interval '1 hour'
    WHERE reservations.client_id = client_name
    RETURNING reservations.device_id;
END $$;

CREATE FUNCTION end_reservations(
    client_name varchar(255),
    serial_ids varchar(255) []
) RETURNS TABLE (
    device_id varchar(255),
    worker_host varchar(255),
    worker_port int
) LANGUAGE plpgsql AS $$ BEGIN
    CREATE TEMPORARY TABLE res (
        device_id varchar(255),
        worker_host varchar(255),
        worker_port int
    ) ON COMMIT DROP;

    INSERT INTO res(device_id)
    SELECT reservations.device_id
    FROM reservations
    WHERE client_id = client_name
        AND reservations.device_id = ANY(serial_ids);

    RETURN QUERY
    SELECT reservations.device_id,
        worker.host,
        worker.port
    FROM res
        INNER JOIN reservations ON res.device_id = reservations.device_id
        INNER JOIN device ON res.device_id = device.id
        INNER JOIN worker ON device.worker_id = worker.id;

    DELETE FROM reservations
    WHERE reservations.device_id IN (
            SELECT res.device_id
            FROM res
        );

    UPDATE device
    SET device_status = 'await_flash_default'
    WHERE device.id IN (
            SELECT res.device_id
            FROM res
        );
END $$;

CREATE FUNCTION end_all_reservations (client_name varchar(255))
RETURNS TABLE (
    device_id varchar(255),
    worker_host varchar(255),
    worker_port int
)
LANGUAGE plpgsql AS $$ BEGIN
    CREATE TEMPORARY TABLE res (
        device_id varchar(255)
    ) ON COMMIT DROP;

    INSERT INTO res(device_id)
    SELECT reservations.device_id
    FROM reservations
    WHERE client_id = client_name;

    RETURN QUERY
    SELECT res.device_id,
        worker.host,
        worker.port
    FROM res
        INNER JOIN reservations ON res.device_id = reservations.device_id
        INNER JOIN device ON res.device_id = device.id
        INNER JOIN worker ON device.worker_id= worker.id;

    DELETE FROM reservations
    WHERE reservations.device_id IN (
            SELECT res.device_id
            FROM res
        );

    UPDATE device
    SET device_status = 'await_flash_default'
    WHERE device.id IN (
            SELECT res.device_id
            FROM res
        );
END $$;

CREATE FUNCTION handle_reservation_timeouts ()
RETURNS TABLE (
    device_id varchar(255),
    client_id varchar(255),
    worker_host varchar(255),
    worker_port int
) LANGUAGE plpgsql AS $$ BEGIN
    CREATE TEMPORARY TABLE res (
       device_id varchar(255)
    ) ON COMMIT DROP;

    INSERT INTO res(device_id)
    SELECT reservations.device_id
    FROM reservations
    WHERE until < CURRENT_TIMESTAMP;
    RETURN QUERY
    SELECT res.device_id,
        reservations.client_id,
        worker.host,
        worker.port
    FROM res
        INNER JOIN reservations ON res.device_id = reservations.device_id
        INNER JOIN device on device.id= res.device_id
        INNER JOIN worker on device.worker_id = worker.id;

    DELETE FROM reservations
    WHERE reservations.device_id IN (
            SELECT res.device_id
            FROM res
        );

    UPDATE device
    SET device_status = 'await_flash_default'
    WHERE device.id IN (
            SELECT res.device_id
            FROM res
        );
END $$;

CREATE FUNCTION get_reservations_ending_soon(mins int)
RETURNS TABLE (
    device_id varchar(255)
)
LANGUAGE plpgsql AS $$ BEGIN
    RETURN QUERY
    SELECT reservations.device_id
    FROM reservations
    WHERE reservations.until < CURRENT_TIMESTAMP + interval '1 second' * mins;
END $$;

CREATE FUNCTION get_device_callback(did varchar(255))
RETURNS TABLE (
    client_id varchar(255)
) LANGUAGE plpgsql AS $$ BEGIN
    IF did NOT IN (
        SELECT id
        FROM device
    ) THEN RAISE EXCEPTION 'Device id does not exist';
    END IF;

    RETURN QUERY
    SELECT reservations.client_id
    FROM reservations
    WHERE did = reservations.device_id;
END $$;
