import os
import sys
import logging
from flask import Flask

# Ensure local repo package is used even if a different version is installed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from treblle_flask import Treblle
import treblle_flask as _treblle_pkg


app = Flask(__name__)

# Configure Treblle explicitly as per installation instructions  
treblle_instance = Treblle(app, TREBLLE_SDK_TOKEN=os.environ.get('TREBLLE_SDK_TOKEN'), TREBLLE_API_KEY=os.environ.get('TREBLLE_API_KEY'))
print(f"Treblle instance created: {treblle_instance}")
print(f"SDK Token set: {bool(treblle_instance._treblle_sdk_token)}")
print(f"API Key set: {bool(treblle_instance._treblle_api_key)}")
print(f"SDK Token: {treblle_instance._treblle_sdk_token}")
print(f"API Key: {treblle_instance._treblle_api_key}")


@app.route("/hello")
def hello():
    return {"hello": "world"}


if __name__ == "__main__":
    # Enable proper DEBUG output 
    import sys
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )
    logging.getLogger('aiohttp.client').setLevel(logging.WARNING)
    logging.getLogger('treblle').debug("Using treblle_flask from: %s", _treblle_pkg.__file__)
    
    # Make Treblle non-blocking for debugging
    from treblle_flask.telemetry_publisher import TelemetryPublisher
    import asyncio
    
    def _send_no_wait(self, payload):
        # schedule the coroutine on the publisher loop and return immediately
        self._event_loop.call_soon_threadsafe(
            asyncio.create_task, self._process_request(payload))
    
    TelemetryPublisher.send_to_treblle = _send_no_wait
    
    # Run: python examples/flask_minimal/app.py
    # Ensure env vars are set:
    #   export TREBLLE_API_KEY=your-project-id
    #   export TREBLLE_SDK_TOKEN=your-api-key
    app.run(debug=True, port=8080)
