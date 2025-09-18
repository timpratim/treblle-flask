import os
import sys
from flask import Flask

# Ensure local repo package is used even if a different version is installed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from treblle_flask import Treblle

app = Flask(__name__)

# Initialize Treblle with your credentials
Treblle(app, TREBLLE_SDK_TOKEN=os.environ.get('TREBLLE_SDK_TOKEN'), TREBLLE_API_KEY=os.environ.get('TREBLLE_API_KEY'))

@app.route('/hello')
def hello():
    return {"hello": "world"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)
