CREATE OR REPLACE PROCEDURE add_worker(
    id varchar(255),
    wurl varchar(255),
    farm_version varchar(255),
    reservables varchar(255) []
)
LANGUAGE plpgsql AS $$ BEGIN
    -- Delete existing worker if present (cascades to devices and reservations)
    DELETE FROM worker WHERE worker.id = add_worker.id;

    INSERT INTO worker (
            id,
            wurl,
            heartbeat,
            farm_version,
            reservables,
            shutting_down
        )
    VALUES (
            id,
            wurl,
            CURRENT_TIMESTAMP,
            farm_version,
            reservables,
            'false'
        );
    END $$;
