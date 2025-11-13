import argparse
import os
import logging
import sys

from client.Client import Client
from client.EventHandler import DefaultEventHandler


def main():
    parser = argparse.ArgumentParser(
        prog="Usbipice client cli",
        description="Connect to remote devices without having to modify existing systems"
    )

    parser.add_argument("amount", help="Amount of devices to connect to")
    parser.add_argument("clientname", help="Name of client")
    parser.add_argument("-f", "-firmware", help="Firmware path to upload to devices")
    parser.add_argument("-p", "-port", help="Port to host subscription server", default="8080")
    parser.add_argument("-c", "--controlserver", help="Control server hostname")
    args = parser.parse_args()

    amount = int(args.amount)
    port = args.p
    name = args.clientname
    firmware = args.f
    curl = args.c

    if not curl:
        curl = os.environ.get("USBIPICE_CONTROL_SERVER")
        if not curl:
            raise Exception("USBIPICE_CONTROL_SERVER not configured, set to url of the control server")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    
    client = Client(name, curl)
    eh = DefaultEventHandler(name, port, logger)

    print("Starting event subscription service...")
    client.startService(port, eh)
    print("Reserving devices...")
    serials = client.reserve(amount)

    if not serials:
        raise Exception("Failed to reserve any devices.")

    if len(serials) != amount:
        client.end(serials)
        raise Exception(f"Requested {amount} devices but only got {len(serials)}. Ending reservation and exiting.")
    
    print(f"Successfully reserved {amount} devices.")
    
    if firmware:
        print("Flashing devices...")

        failed = client.flash(serials, firmware, 60)

        if failed:
            client.end(serials)
            raise Exception(f"{len(failed)} devices failed to flash. Ending reservation and exiting.")
        
        print("Flashing successful!")
    
    print("Devices are now ready. Press enter to end the session. Note that this will free the reserved devices.")
    input()
    client.end(serials)
    client.stopService()
    print("Session ended.")

if __name__ == "__main__":
    main()
