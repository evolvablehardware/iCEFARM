CREATE OR REPLACE FUNCTION reservation_end()
RETURNS trigger
AS $$ BEGIN
    PERFORM pg_notify('reservation_updates', format('{"device_id": %I, "client_id": %I}', OLD.device_id, OLD.client_id));
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER reservation_end_trigger
AFTER DELETE ON reservations
FOR ROW
EXECUTE FUNCTION reservation_end();

CREATE OR REPLACE FUNCTION device_available()
RETURNS trigger
AS $$
DECLARE amount int8;
BEGIN
    SELECT COUNT(*) INTO amount FROM device WHERE device_status = 'available';
    PERFORM pg_notify('device_available', format('%L', amount));
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER device_available_trigger
AFTER UPDATE ON device
FOR ROW
WHEN (OLD.device_status != 'available' AND NEW.device_status = 'available')
EXECUTE FUNCTION device_available();