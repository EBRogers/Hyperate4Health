# HypeRate Recorder

The ```Recorder``` class is a Python class for recording heart rate data from the Hyperate app. The class uses a WebSocket connection to receive heart rate updates from the Hyperate app and saves the data to a CSV file.Dependencies

The ```Recorder``` class requires the following dependencies:
- ```pandas``` library for data manipulation and storage
- ```websocket``` library for WebSocket communication
- ```csv``` library for writing data to CSV files
- ```os``` and ```time``` libraries for file path manipulation and timestamp generation

These libraries can be installed using the ```pip``` package manager.

## Usage

To use the ```Recorder``` class, create an instance of the class and call the ```begin_recording``` method. 

The constructor for the class requires the following arguments:
- ```hyperate_id``` (str): the ID of the Hyperate device to record heart rate data from
- ```save_path``` (str): the path to save the heart rate data CSV file to. It is assumed to be a directory, unless it ends in .csv - otherwise a filename is autogenerated with this format: `[Hyperate_ID]_YYYYmmdd_HHMM.csv`
- ```timeout``` (int, optional): the time in seconds after which to stop recording if no heart rate updates are received. Defaults to 30 seconds.
- ```api_key``` (str, optional): the API key for the Hyperate app. If not provided, the API key will be loaded from the ```HYPERATE_API_KEY``` environmental variable.

For example, to record heart rate data from a device with ID ```AB12``` and save the data to a file called ```hr_data.csv``` in the current directory, you can use the following code:
```python
from HypeRate_websocket_handler import Recorder

recorder = Recorder(hyperate_id='AB12', save_path='hr_data.csv')
recorder.begin_recording()
```

If you wanted to save it in a different directory with the auto generated name, simply pass the directory as `save_path` without specifying a .csv file name.
```python
from HypeRate_websocket_handler import Recorder

recorder = Recorder(hyperate_id='AB12', save_path='/Users/HypeRateUser/Documents')
recorder.begin_recording()
```

The ```begin_recording``` method starts the WebSocket connection and begins recording heart rate data. The data is saved to the specified CSV file, with a new row added for each heart rate update received. If no heart rate updates are received for the specified timeout period, the recording will stop automatically.

Heart rate data are saved to the csv file as websocket messages come in. Do not move or delete the csv file during operation of the recorder. If you specify a name of a file that already exists, or start multiple instances of `Recorder` with the same `save_path` directory within 1 minute of each other, it will be overwritten. 

The csv will contain a header on the first line with two columns: 
- `UNIT_TIMESTAMP` the seconds since 1/1/1970 00:00 when the heart rate message **was received**
- `HR` integer heart rate

Keep in mind that the duration between timestamps will vary.

An example:
```
UNIX_TIMESTAMP,HR
1676039238.726014,72
1676039243.0965729,74
1676039246.97718,72
1676039252.811679,73
```


## Notes

According to [HypeRate's API documentation](https://github.com/HypeRate/DevDocs/blob/e172947262deadbd39f644f19b30d56847bd5ea5/Readme.md) (when this project was created in Feb 2023), the HypeRate server must receive a heart beat every 30 seconds to keep the connection open. `Recorder` uses a `threading.Timer` to automatically to send a heartbeat every 20 seconds just to be safe.

`Recorder` also uses another `threading.Timer` to close the websocket and stop recording if the amount of time specified in the `timeout` argument passes without a message.

`Recorder` was designed as a starting point to satisfy a specific research need - recording HR data from wearables over the internet. That being said, it has not been extensively tested for thread safety outside basic scripts.

**If you have any questions, comments, or suggestions please reach out!**

## Acknowledgements
This project would not have been possible without the HypeRate team, and all of their amazing work. Thank you HypeRate!

## License
Copyright (c) 2023 Ethan Rogers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.