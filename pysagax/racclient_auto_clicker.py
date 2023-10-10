import multiprocessing
import threading
import time
import tkinter

import pysagax
from pysagax.racclient import Client, on_close

root = None



class ClickerRobot(threading.Thread):
    def __init__(self, client: Client) -> None:
        super().__init__()
        self.client = client
        self.stop: bool = False

    def run(self) -> None:
        
        freq_values = ["300M", "350M", "399.7M", "446M"]
        roif_values = ["300.1M", "350.1M", "399.8M", "446.05M"]
        db_values = ["20", "60", "100"]
        bin_count = ["128", "512", "1024", "4096", "32768"]
        
        while not self.stop:
            self.client.client_window.connect_commands()
            print("Clicked Connect")
            time.sleep(2)

            freq_values = freq_values[1:] + freq_values[:1]
            roif_values = roif_values[1:] + roif_values[:1]
            db_values = db_values[1:] + db_values[:1]
            bin_count = bin_count[1:] + bin_count[:1]
            print(f"CONFIG: freq={freq_values[0]}, db={db_values[0]}, bin_count={bin_count[0]}")
            self.client.client_window.control_frame.freq_string.set(freq_values[0])
            self.client.client_window.control_frame.roi_center_string.set(freq_values[0])
            self.client.client_window.control_frame.freq_string.set(roif_values[0])
            self.client.client_window.control_frame.gain_string.set(db_values[0])
            self.client.client_window.control_frame.bin_count_string.set(bin_count[0])


            self.client.client_window.control_frame.start_commands()
            print("Clicked Start")
            time.sleep(25)

            self.client.client_window.control_frame.rec_commands()
            print("Clicked Recording Start")
            time.sleep(15)

            
            self.client.client_window.control_frame.rec_commands()
            print("Clicked Recording Stop")
            time.sleep(15)

            
            self.client.client_window.disconnect_commands()
            print("Clicked Disconnect")
            time.sleep(2)


def main() -> None:
    global root
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = Client(root)
    root.geometry("1200x850")
    root.wm_title(f"Sagax Direction Finder Client Application {pysagax.__version__}")
    root.protocol("WM_DELETE_WINDOW", on_close)
    clicker = ClickerRobot(ex)
    clicker.start()
    root.mainloop()


if __name__ == "__main__":
    main()