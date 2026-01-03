"""Makes it possible for a specific device state to be requested from the client."""
from typing import List

state_value_checkers = {}
state_reservation_constructors = {}

def get_registered_reservables() -> List[str]:
    return list(state_reservation_constructors.keys())

def get_reservation_state_fac(state, kind, args):
    """Creates a factory for switching states based on a reservation request.
    Returns False if the event does not contain the correct arguments for the
    requested state or the state does not exist."""
    fn = state_reservation_constructors.get(kind)

    if not fn:
        return False

    return fn(state, args)

def reservable(name, *args: List[str]):
    """Makes an AbstractState available by reservation request under name. When reserve is called with
    this name, the device switches state to Cls(device: device.Device, *json_args), where json_args
    are obtained from using args as keys into the request dictionary. The class should be included in
    __init__.py to ensure the decorator is run.

    Ex.
    >>> @reservable("print device", "message")
        class ExampleState(device.state.core.AbstractState):
                def __init__(self, state, msg):
                    super().__init__()
                    self.logger.info(msg)
    >>> requests.get("{host}/reserve", json={
            "serial": "ASDF39TFDFG",
            "message": "hello!"
        })
    [ASDf39TFDFG] state is now ExampleState
    [ASDf39TFDFG] hello!
    """
    def res(cls):
        if name in state_reservation_constructors:
            raise Exception(f"reservable {name} is already registered (cls {cls})")

        def check_state(event):
            for arg in args:
                if not event.get(arg):
                    return False

            return True

        state_value_checkers[name] = check_state

        def make_state_fac(state, event):
            json_args = []

            for arg in args:
                json_args.append(event.get(arg))

            return lambda : cls(state, *json_args)

        state_reservation_constructors[name] = make_state_fac

        return cls

    return res
