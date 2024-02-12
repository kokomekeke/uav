from concurrent.futures import ThreadPoolExecutor, wait

from pysagax.communication.req_rep import REQ, REP

client = REQ()
server = REP()

pool = ThreadPoolExecutor()

def request():
    while True:
        message = "Hello"

        print("CLIENT: ==========")
        print(f"CLIENT: Sending {message}")
        response = client.send(message.encode())
        print(f"CLIENT: Received {response.decode()}")

def reply():
    while True:
        response = "World"

        print("SERVER: ==========")
        message = server.recv()
        print(f"SERVER: Received {message.decode()}")

        print(f"SERVER: Sending {response}")
        server.resp(response.encode())

p = pool.submit(reply)
q = pool.submit(request)

while True:
    done, running = wait((p, q), timeout=1)

    print(f"Done: {done}")
    print(f"Running: {running}")

    for future in done:
        if future.exception(0) is not None:
            raise future.exception()

