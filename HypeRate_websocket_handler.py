import argparse
import json
import os
import time
from csv import writer
from threading import Timer
from typing import Optional
import pandas as pd
import rel
import websocket


# This program was written by Ethan Rogers (Personal Health Informatics, Northeastern University, Boston, MA)
# It is distributed ** AS IS ** under the MIT license. See 'License' in README.md
# https://github.com/EBRogers/Hyperate4Health
# Special thanks to Hendrikje Wagner (HypeRate COO) and the HypeRate Team (HypeRate.io)
# Their work enables our research.

class Recorder:

    def __init__(
            self,
            hyperate_id: str,
            save_path: str,
            timeout: int = 30,
            api_key: Optional[str] = None
    ):
        # Parameter Validation: API Key
        self.api_key = api_key or os.environ.get('HYPERATE_API_KEY')
        if not self.api_key:
            raise AttributeError(
                "You must either pass the API Key as the parameter 'api_key' or set the API key as an environmental "
                "variable. This can be loaded automatically by placing a '.env' file in the working directory of this "
                "program, and with the text: API_KEY = \"[PUT YOUR KEY HERE]\" and calling load_dotenv() from the "
                "'dotenv' packege"
            )
        # Parameter Validation: Hyperate ID
        if not isinstance(hyperate_id, str):
            raise TypeError(
                "ID must be a string like 'AB12' or 'XY89' and is generated when you run the HypeRate app on your smartphone or measurement device.")
        # Parameter Validation: save path
        if not isinstance(save_path, str):
            raise TypeError("save_path must be a string.")
        # Parameter Validation: Timeout
        if not isinstance(timeout, int):
            try:
                timeout = int(timeout)
            except ValueError:
                raise TypeError("ID must be a string.")
        if timeout < 0 or timeout > 86400:
            raise ValueError("Timeout can't be less than 0 or more than a day.")
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
            file_name = f"HR_{self.id}_{time.strftime('%Y%m%d_%H%M')}.csv"
            self.save_path = os.path.join(save_path, file_name)
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        with open(self.save_path, 'w') as f_object:
            writer_object = writer(f_object)
            writer_object.writerow(['UNIX_TIMESTAMP', 'HR'])

        # make the websocket and run it for a while
    def begin_recording(self):
        self.ws = self._make_websock()
        self._run_websock()

    # Websocket Starters
    def _make_websock(self):
        return websocket.WebSocketApp(self.address,
                                      on_open=self._on_open,
                                      on_message=self._on_message,
                                      on_error=self._on_error,
                                      on_close=self._on_close)

    def _run_websock(self):
        self.ws.run_forever(dispatcher=rel)
        # self.ws.run_forever(dispatcher=rel, reconnect=5)
        # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
        rel.signal(2, self.stop)  # Keyboard Interrupt
        rel.dispatch()

    # Websocket on_action Function
    def _on_message(self, ws, message):
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
                if os.path.exists(self.save_path):
                    with open(self.save_path, 'a') as f_object:
                        writer_object = writer(f_object)
                        writer_object.writerow([time.time(), m['payload']['hr']])
                else:
                    print(f"WARNING: Original file was moved or deleted. Re-saving entire dataset as {self.save_path}")
                    self.data.to_csv(self.save_path, index=False)
            except Exception as e:
                print(e)
                print(
                    f"ERROR OCCURRED WHEN SAVING: CRASH SAVING TO {self.save_path}.")
                self.data.to_csv(self.save_path, index=False)
                self.stop()

    def _on_error(self, ws, error):
        # print('on_error: ON ERROR CALLED')
        print(error)

    def _on_close(self, ws, close_status_code, close_msg):
        # print("on_close: ### closed ###")
        self.stop()

    def _on_open(self, ws):
        # print("on_open: Opened connection")
        ws.send(json.dumps(self.params))
        # print("on_open: timer_set")
        self._start_beats()
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

    # Beat Initializers
    def _start_beats(self):
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
                        help='Optional. This argument specifies the minimum time allowed between HR signals for the '
                             'connection to remain open and the program to be running.')
    parser.add_argument('--api_key', type=str, default=None, required=False,
                        help='Optional. This argument provides the API key to the recorder. If you do not specify, '
                             'it will be automatically loaded from the "HYPERATE_API_KEY" environmental variable')
    args = parser.parse_args()

    websocket.enableTrace(False)
    w = Recorder(args.id, args.save_path, timeout=args.timeout)
    w.begin_recording()

    # hyperate_id: str, save_path: str, timeout: int = 15
