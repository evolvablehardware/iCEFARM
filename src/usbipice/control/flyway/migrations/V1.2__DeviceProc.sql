CREATE PROCEDURE add_device(did varchar(255), wid varchar(255))
LANGUAGE plpgsql AS $$ BEGIN
    IF worker NOT IN (
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