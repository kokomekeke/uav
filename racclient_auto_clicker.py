import multiprocessing
import threading
import time
import tkinter

import pysagax
from racclient import Client, on_close


class ClickerRobot(threading.Thread):
    def __init__(self, client: Client) -> None:
        super().__init__()
        self.client = client
        self.stop: bool = False

    def run(self) -> None:
        while not self.stop:
            self.client.client_window.connect_commands()
            print("Clicked Connect")
            time.sleep(2)

            self.client.client_window.disconnect_commands()
            print("Clicked Disconnect")
            time.sleep(2)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = Client(root)
    root.geometry("1200x850")
    root.wm_title(f"Sagax Direction Finder Client Application {pysagax.__version__}")
    root.protocol("WM_DELETE_WINDOW", on_close)
    clicker = ClickerRobot(ex)
    clicker.start()
    root.mainloop()
