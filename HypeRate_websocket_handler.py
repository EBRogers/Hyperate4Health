import argparse
import json
import os
import time
from csv import writer
from threading import Timer

import pandas as pd
import rel
import websocket
from dotenv import load_dotenv


# This program was written by Ethan Rogers (Personal Health Informatics, Northeastern University, Boston, MA)
# https://github.com/EBRogers/Hyperate4Health
# Special thanks to Hendrikje Wagner (HypeRate COO) and the HypeRate Team (HypeRate.io)
# Their work enables our research.

class recorder:

    def __init__(self, hyperate_id: str, save_path: str, timeout: int = 30):

        # Parameter Validation
        try:
            self.api_key = os.environ['API_KEY']
        except KeyError:
            raise AttributeError("You must set the API key as an environmental variable. This can be loaded "
                                 "automatically by placing a '.env' file in the working directory of this program, "
                                 "and with the text: API_KEY = \"[PUT YOUR KEY HERE]\"")
        if type(hyperate_id) != str:
            raise AttributeError("ID must be a string.")

        if type(save_path) != str:
            raise AttributeError("save_path must be a string.")

        if type(timeout) != int:
            try:
                timeout = int(timeout)
            except TypeError:
                raise AttributeError("ID must be a string.")
        if timeout < 0 or timeout > 86400:
            raise AttributeError("Timeout can't be less than 0 or more than a day.")

        # Init some vars
        self.id = hyperate_id
        self.timeout = timeout
        self.params = {"topic": f"hr:{self.id}", "event": "phx_join", "payload": {}, "ref": 0}
        self.address = f"wss://app.hyperate.io/socket/websocket?token={self.api_key}"
        self.response_beat = None
        self.close_beat = None
        self.last_hr_ts = 0
        self.start_time = time.time()
        self.data = pd.DataFrame(columns=["UNIX_TIMESTAMP", "HR"])

        # Determine the name and save path, create save dir, and file to save to
        if save_path.endswith(".csv"):
            self.save_path = save_path
        else:
            file_name = f"HR_{self.id}_{time.strftime('%Y%d%m_%H%M')}.csv"
            self.save_path = os.path.join(save_path, file_name)
        if not os.path.exists(os.path.dirname(self.save_path)):
            os.makedirs(os.path.dirname(self.save_path))
        with open(self.save_path, 'w') as f_object:
            writer_object = writer(f_object)
            writer_object.writerow(['UNIX_TIMESTAMP', 'HR'])
            f_object.close()

        # make the websocket and run it for a while
        self.ws = self.make_websock()
        self.run_websock()

    # Websocket Starters
    def make_websock(self):
        return websocket.WebSocketApp(self.address,
                                      on_open=self.on_open,
                                      on_message=self.on_message,
                                      on_error=self.on_error,
                                      on_close=self.on_close)

    def run_websock(self):
        self.ws.run_forever(dispatcher=rel)
        # self.ws.run_forever(dispatcher=rel, reconnect=5)
        # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
        rel.signal(2, rel.abort)  # Keyboard Interrupt
        rel.dispatch()

    # Websocket on_action Function
    def on_message(self, ws, message):
        # print(f"on_message: {message}")
        m = json.loads(message)
        if m['event'] == "hr_update":
            self.close_beat.cancel()
            self.close_beat = Timer(self.timeout, self.stop)
            self.close_beat.start()
            print(f"{self.id} {time.strftime('%m/%d/%Y %H:%M:%S')} {m['payload']['hr']}")
            self.data = pd.concat([self.data, pd.Series({'UNIX_TIMESTAMP': time.time(),
                                                         "HR": m['payload']['hr']}).to_frame().T])
            try:
                with open(self.save_path, 'a') as f_object:
                    writer_object = writer(f_object)
                    writer_object.writerow([time.time(), m['payload']['hr']])
                    f_object.close()
            except Exception as e:
                print(e)
                print(
                    f"SOME ERROR OCCURRED WHEN SAVING: CRASH SAVING TO {self.save_path}.\nDo not move or alter file "
                    f"when running.")
                self.data.to_csv(self.save_path, index=False)
                self.stop()

    def on_error(self, ws, error):
        # print('on_error: ON ERROR CALLED')
        print(error)

    def on_close(self, ws, close_status_code, close_msg):
        # print("on_close: ### closed ###")
        self.stop()

    def on_open(self, ws):
        # print("on_open: Opened connection")
        ws.send(json.dumps(self.params))
        # print("on_open: timer_set")
        self.start_beats()
        print(
            f"Connection to Hyperate established with ID {self.id}\n(i) For a better visual go to: app.hyperate.io/{self.id}")

    # Beat Functions
    def respond_to_keep_open(self):
        try:
            self.ws.send(json.dumps({
                "topic": "phoenix",
                "event": "heartbeat",
                "payload": {},
                "ref": 0
            }))
            # print("respond_to_keep_open: sent HR, timer_set")
            self.response_beat = Timer(20, self.respond_to_keep_open)
            self.response_beat.start()
        except websocket._exceptions.WebSocketConnectionClosedException:
            self.stop()

    def get_last_message_ts(self):
        return self.data.UNIX_TIMESTAMP.max()

    # Beat Initializers
    def start_beats(self):
        self.response_beat = Timer(20, self.respond_to_keep_open)
        self.close_beat = Timer(self.timeout, self.stop)
        self.response_beat.start()
        self.close_beat.start()

    # Shut down code
    def stop(self):
        print("Stopping...")
        try:
            self.ws.close()
        except websocket._exceptions.WebSocketConnectionClosedException:
            pass
        self.close_beat.cancel()
        self.response_beat.cancel()
        rel.abort()

    def get_most_recent_HR(self):
        return self.data.loc[self.data.TIMESTAMP == self.data.TIMESTAMP.max()].copy(deep=True)

    def get_all_HR(self):
        return self.data.copy(deep=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='HypeRate Heartrate Recorder',
        description='This program uses the HypeRate API to record the heartrate stream from a HypeRate device ID, '
                    'and save it to a csv file.',
        epilog='Thank you to HypeRate for making this possible!')
    parser.add_argument('id', type=str, help="The HypeRate device ID. Example: AB12")
    parser.add_argument('save_path', type=str, help="The path to where you want to save the file. To "
                                                    "override default file naming, you can specify a "
                                                    "filename ending in .csv\nExample: "
                                                    "/user/Documents\nExample: "
                                                    "/user/Documents/HR.csv\n(i) If the file exists "
                                                    "already, it will be overriden.")
    # argument
    parser.add_argument('--timeout', type=int, default=30, required=False,
                        help='Optional. This argument specfies the minimum time allowed between HR signals for the '
                             'connection to remain open and the program to be running.')
    args = parser.parse_args()
    load_dotenv()
    websocket.enableTrace(False)
    w = recorder(args.id, args.save_path, timeout=args.timeout)

    # hyperate_id: str, save_path: str, timeout: int = 15
