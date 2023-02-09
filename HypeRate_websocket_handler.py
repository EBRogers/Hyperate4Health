import json, os, time
from threading import Timer
import websocket
import rel
import pandas as pd

from dotenv import load_dotenv


class recorder:

    def __init__(self, id: str, save_path: str, timeout: int = 15):

        # Parameter Validation
        try:
            self.api_key = os.environ['API_KEY']
        except KeyError:
            raise AttributeError("You must set the API key as an environmental variable. This can be loaded "
                                 "automatically by placing a '.env' file in the working directory of this program, "
                                 "and with the text: API_KEY = \"[PUT YOUR KEY HERE]\"")
        if type(id) != str:
            raise AttributeError("ID must be a string.")

        if type(save_path) != str:
            raise AttributeError("save_path must be a string.")

        elif ~os.path.isdir(save_path):
            raise AttributeError("save_path must be a directory. ")

        if type(timeout) != int:
            try:
                timeout = int(timeout)
            except TypeError:
                raise AttributeError("ID must be a string.")
        if timeout < 0 or timeout > 86400:
            raise AttributeError("Timeout can't be less than 0 or more than a day.")

        # Init some vars
        self.id = id
        self.timeout = timeout
        self.params = {"topic": f"hr:{self.id}", "event": "phx_join", "payload": {}, "ref": 0}
        self.address = f"wss://app.hyperate.io/socket/websocket?token={self.api_key}"
        self.response_beat = None
        self.close_beat = None
        self.last_hr_ts = 0
        self.start_time = time.time()
        self.data = pd.DataFrame(columns=["UNIX_TIMESTAMP", "HR"])

        # Determine the name and save path
        if save_path.endswith(".csv"):
            self.save_path = save_path
        else:
            file_name=f"HR_{self.id}_{time.strftime('%Y%d%m_%H%M')}.csv"
            self.save_path = os.path.join(save_path,file_name)
        if ~os.path.exists(os.path.dirname(self.save_path)):
            os.makedirs(os.path.dirname(self.save_path))

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
        print(f"on_message: {message}")
        m = json.loads(message)
        if m['event'] == "hr_update":
            self.data = pd.concat([self.data, pd.Series({'UNIX_TIMESTAMP': time.time(),
                                                         "HR": m['payload']['hr']}).to_frame().T])
    def on_error(self, ws, error):
        print('on_error: ON ERROR CALLED')
        self.save()
        print(error)

    def on_close(self, ws, close_status_code, close_msg):
        print("on_close: ### closed ###")
        self.save(restart_beat=False)
        self.cancel_beats()

    def on_open(self, ws):
        print("on_open: Opened connection")
        ws.send(json.dumps(self.params))
        print("on_open: timer_set")
        self.start_beats()

    # Beat Functions
    def respond_to_keep_open(self):
        self.ws.send(json.dumps({
            "topic": "phoenix",
            "event": "heartbeat",
            "payload": {},
            "ref": 0
        }))
        print("respond_to_keep_open: sent HR, timer_set")
        self.response_beat = Timer(20, self.respond_to_keep_open)
        self.response_beat.start()

    def continue_or_close(self):
        last_message_ts = self.get_last_message_ts()
        print(f"tdelta = {time.time() - last_message_ts}")
        if time.time() - last_message_ts > self.timeout:
            self.ws.close()
            # self.cancel_beats()
        else:
            self.close_beat = Timer(self.timeout, self.continue_or_close)
            self.close_beat.start()

    def save(self, restart_beat=True):
        self.data.to_csv(self.save_path, index=False)
        if restart_beat:
            self.save_beat = Timer(20, self.save)
            self.save_beat.start()

    def get_last_message_ts(self):
        return self.data.UNIX_TIMESTAMP.max()

    # Beat Initializers and Terminators
    def start_beats(self):
        self.response_beat = Timer(20, self.respond_to_keep_open)
        self.close_beat = Timer(self.timeout, self.continue_or_close)
        self.save_beat = Timer(20, self.save)

        self.response_beat.start()
        self.close_beat.start()
        self.save_beat.start()

    def cancel_beats(self):
        self.close_beat.cancel()
        self.response_beat.cancel()
        self.save_beat.cancel()
        rel.abort()


if __name__ == "__main__":
    load_dotenv()
    websocket.enableTrace(False)
    w = recorder("FC52", "./data/test.csv")
