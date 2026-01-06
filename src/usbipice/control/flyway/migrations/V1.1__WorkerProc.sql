CREATE PROCEDURE add_worker(
    id varchar(255),
    host varchar(255),
    port int,
    farm_version varchar(255),
    reservables varchar(255) []
)
LANGUAGE plpgsql AS $$ BEGIN
    IF name IN (
        SELECT worker.name
        FROM worker
    ) THEN RAISE EXCEPTION 'Worker id already exists';
    END IF;

    INSERT INTO worker (
            id,
            host,
            port,
            heartbeat,
            farm_version,
            reservables,
            shutdown_down
        )
    VALUES (
            id,
            host,
            port,
            CURRENT_TIMESTAMP,
            farm_version,
            reservables,
            'false'
        );
    END $$;

    CREATE PROCEDURE shutdown_worker(wid varchar(255))
    LANGUAGE plpgsql AS $$ BEGIN
    UPDATE worker
    SET shutdown_down = 'true'
    WHERE id = wid;
END $$;

CREATE FUNCTION remove_worker(wid varchar(255))
RETURNS TABLE (
    client_id varchar(255),
    device_id varchar(255)
)
LANGUAGE plpgsql AS $$ BEGIN
    IF wid NOT IN (
        SELECT id
        FROM worker
    ) THEN RAISE EXCEPTION 'Worker id does not exist';
    END IF;

    RETURN QUERY
    SELECT device_id, client_id
    FROM reservations
        INNER JOIN device on device_id = device.device_id
    WHERE device.worker_id = wid;

    DELETE FROM worker
    WHERE id = wid;
    END $$;

    CREATE PROCEDURE heartbeat_worker(wid varchar(255))
    LANGUAGE plpgsql AS $$ BEGIN
    IF wid NOT IN (
        SELECT id
        FROM worker
    ) THEN RAISE EXCEPTION 'Worker id does not exist';
    END IF;

    UPDATE worker
    SET heartbeat = CURRENT_TIMESTAMP
    WHERE id = wid;
END $$;

CREATE FUNCTION handle_worker_timeouts(s int)
RETURNS TABLE (
    serial_id varchar(255),
    client_id varchar(255),
    worker_id varchar(255)
)
LANGUAGE plpgsql AS $$
DECLARE t timestamp;
BEGIN
    t := CURRENT_TIMESTAMP - s * interval '1 second';
    RETURN QUERY
    SELECT device.id,
        reservations.client_id,
        worker.id
    FROM worker
        INNER JOIN device ON worker.id = device.worker_id
        INNER JOIN reservations ON reservations.device_id = device.id
    WHERE heartbeat < t;

    DELETE FROM worker
    WHERE heartbeat < t;
END $$;