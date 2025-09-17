<div align="center">
  <img src="https://github.com/user-attachments/assets/b268ae9e-7c8a-4ade-95da-b4ac6fce6eea"/>
</div>
<div align="center">

# Treblle

<a href="https://docs.treblle.com/en/integrations" target="_blank">Integrations</a>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<a href="http://treblle.com/" target="_blank">Website</a>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<a href="https://docs.treblle.com" target="_blank">Docs</a>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<a href="https://blog.treblle.com" target="_blank">Blog</a>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<a href="https://twitter.com/treblleapi" target="_blank">Twitter</a>
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
<a href="https://treblle.com/chat" target="_blank">Discord</a>
<br />

  <hr />
</div>

API Intelligence Platform. 🚀

Treblle is a lightweight SDK that helps Engineering and Product teams build, ship & maintain REST-based APIs faster.

## Features

<div align="center">
  <br />
  <img src="https://github.com/user-attachments/assets/02afd9f5-ab47-48ff-929a-0f3fcddcca34"/>
  <br />
  <br />
</div>

- [API Monitoring & Observability](https://www.treblle.com/features/api-monitoring-observability)
- [Auto-generated API Docs](https://www.treblle.com/features/auto-generated-api-docs)
- [API analytics](https://www.treblle.com/features/api-analytics)
- [Treblle API Score](https://www.treblle.com/features/api-quality-score)
- [API Lifecycle Collaboration](https://www.treblle.com/features/api-lifecycle)
- [Native Treblle Apps](https://www.treblle.com/features/native-apps)


## treblle-flask

Treblle makes it super easy to understand what’s going on with your APIs and the apps that use them.
Just by adding Treblle to your API out of the box you get:

- Real-time API monitoring and logging
- Auto-generated API docs with OAS support
- API analytics
- Quality scoring
- One-click testing
- API management on the go and more...


## Requirements

- python 3.7+
- aiohttp

## Installation

```bash
pip install treblle-flask
```

## Quick Start

Use Treblle by importing the `Treblle` class and passing your Flask app to the constructor along with your SDK token and API key.

```python
from flask import Flask
from treblle_flask import Treblle

app = Flask(__name__)

# Initialize Treblle with your credentials
Treblle(app, TREBLLE_SDK_TOKEN="YOUR_SDK_TOKEN", TREBLLE_API_KEY="YOUR_API_KEY")

@app.route('/hello')
def hello():
    return {"hello": "world"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

Run it:

```bash
python app.py
```

## Configure With Environment Variables

Set the following environment variables and initialize Treblle without arguments:

- `TREBLLE_SDK_TOKEN`: Your Treblle SDK token
- `TREBLLE_API_KEY`: Your Treblle API key

```bash
export TREBLLE_SDK_TOKEN="YOUR_SDK_TOKEN"
export TREBLLE_API_KEY="YOUR_API_KEY"
```

```python
from flask import Flask
from treblle_flask import Treblle

app = Flask(__name__)

# Reads credentials from environment variables
Treblle(app)

@app.route('/hello')
def hello():
    return {"hello": "world"}
```


## Advanced Usage

Optional configuration options help customize behavior:

- `hidden_keys`: List of keys to mask in request/response payloads. A default set of sensitive keys is used if omitted.
- `mask_auth_header`: Whether to mask the `Authorization` header value (scheme stays visible). Default: `True`.
- `limit_request_body_size`: Max request size captured. Larger bodies are skipped. Default: 4 MiB.
- `request_transformer`: Function to transform request body bytes into a JSON-serializable object.
- `response_transformer`: Function to transform response body bytes into a JSON-serializable object.

```python
from flask import Flask
from treblle_flask import Treblle

def request_transformer(raw_bytes: bytes):
    # Example: parse JSON and strip large fields
    import json
    try:
        data = json.loads(raw_bytes.decode("utf-8", "replace"))
    except Exception:
        return {}
    data.pop("debug_dump", None)
    return data

def response_transformer(raw_bytes: bytes):
    # Example: parse JSON and redact sensitive fields
    import json
    try:
        data = json.loads(raw_bytes.decode("utf-8", "replace"))
    except Exception:
        return {}
    if "token" in data:
        data["token"] = "***"
    return data

app = Flask(__name__)

Treblle(
    app,
    TREBLLE_SDK_TOKEN="YOUR_SDK_TOKEN",
    TREBLLE_API_KEY="YOUR_API_KEY",
    hidden_keys=["password", "secret", "authorization"],
    mask_auth_header=True,
    limit_request_body_size=4 * 1024 * 1024,
    request_transformer=request_transformer,
    response_transformer=response_transformer,
)
```

Notes:

- Transformers must return JSON-serializable objects.
- Request transformers read the whole request body into memory.
- Response transformer does not run for streaming responses.
