import blacksheep
import uvicorn
import subprocess

if __name__ == "__main__":
    uvicorn.run("client:app", host="0.0.0.0", port=5050)
else:
    app = blacksheep.Application()

@blacksheep.get("/{address}/{busid}")
def connect(address: str, busid: str):
    print(f"bus: {busid}")
    # https://docs.python.org/3/library/subprocess.html#security-considerations
    # as long as we don't enable shell mode, we don't have to worry about injections
    p = subprocess.run(["sudo", "usbip", "attach", "-r", address, "-b", busid])
    if p.returncode != 0:
        print(f"Failed to connect to {address} {busid}")

    return blacksheep.Response(200)
