CREATE OR REPLACE FUNCTION reservation_end()
RETURNS trigger
AS $$ BEGIN
    PERFORM pg_notify('reservation_updates', format('{device_id: %L, client_id: %L}', OLD.device_id, OLD.client_id));
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER reservation_end_trigger
AFTER DELETE ON reservations
FOR ROW
EXECUTE FUNCTION reservation_end();