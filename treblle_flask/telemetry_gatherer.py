# coding=utf-8

"""
treblle_flask.telemetry_gatherer
~~~~~~~~~~~~~~~~~~~~~~~

This module implements the TelemetryGatherer class, which is responsible for gathering telemetry data
about the server, request and response objects, and any unhandled errors which occured during the requests.
It generates a payload to send to Treblle backend.

You shouldn't use this class directly, instead use Treblle class from the extension module.
"""

import base64
import re
from copy import deepcopy
from datetime import datetime, timezone
from flask import request, g
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from os import environ
from platform import python_version, system, release, machine
from socket import getaddrinfo, gethostname, AF_INET
from time import time
from traceback import extract_tb
from types import GeneratorType
from uuid import uuid4

logger = getLogger('treblle')


class TelemetryGatherer:
    # Common authentication schemes, if authorization header starts with one of these strings, we'll mask the value,
    # but keep the scheme visible. Otherwise, we'll mask the entire header to be safe.
    COMMON_AUTH_SCHEMES = {'Basic', 'Bearer', 'Digest', 'Negotiate', 'OAuth', 'AWS4-HMAC-SHA256', 'HOBA', 'Mutual'}
    
    # Sensitive headers that should always be masked
    SENSITIVE_HEADERS = {'authorization', 'x-api-key'}
    
    # Maximum response body size (2MB)
    MAX_RESPONSE_BODY_SIZE = 2 * 1024 * 1024

    def __init__(
        self, treblle_sdk_token, treblle_api_key, hidden_keys, mask_auth_header, limit_request_body_size,
        request_transformer, response_transformer, ignored_environments, debug
    ):
        """
        Gathers telemetry data about the server, request and response objects, and any unhandled errors which occured
        during the requests and generates a payload to send to Treblle backend.

        You shouldn't use this class directly, instead use Treblle class from the extension module.
        """

        self._hidden_keys = set(key.lower() for key in hidden_keys) if hidden_keys else set()
        self._should_mask_auth_header = mask_auth_header
        self._limit_request_body_size = limit_request_body_size
        self._request_transformer = request_transformer
        self._response_transformer = response_transformer
        self._ignored_environments = set(env.strip().lower() for env in ignored_environments) if ignored_environments else {'dev', 'test', 'testing'}
        self._debug = debug
        
        # Check if current environment should be ignored
        current_env = environ.get('FLASK_ENV', environ.get('ENV', 'production')).lower()
        self._disabled = not treblle_sdk_token or not treblle_api_key or current_env in self._ignored_environments

        try:
            addrinfo = getaddrinfo(gethostname(), None)
            host_ip = [host for family, *_, host in addrinfo if family == AF_INET][0][0]
        except (OSError, IndexError):
            host_ip = 'bogon'

        # Get server timezone, default to UTC if unable to determine
        try:
            server_timezone = datetime.now(timezone.utc).astimezone().tzinfo.tzname(None) or 'UTC'
        except:
            server_timezone = 'UTC'

        self._payload_template = {
            'project_id': treblle_api_key, 'api_key': treblle_sdk_token,
            'sdk': 'flask', 'version': 1,
            'data': {
                'server': {
                    'ip': host_ip,
                    'timezone': server_timezone,
                    'os': {'name': system() or 'Unknown', 'release': release() or 'Unknown', 'architecture': machine() or 'Unknown'},
                    'software': 'Flask',
                    'protocol': 'HTTP/1.1',
                },
                'language': {'name': 'python', 'version': python_version() or 'Unknown'},
                'errors': []
            }
        }

    def _is_base64_image(self, value):
        """Check if value is a base64 encoded image"""
        if not isinstance(value, str) or len(value) < 100:
            return False
        
        # Check for common base64 image patterns
        base64_image_pattern = r'^data:image/[a-zA-Z]*;base64,[A-Za-z0-9+/]+={0,2}$'
        if re.match(base64_image_pattern, value):
            return True
        
        # Check for raw base64 that might be an image (heuristic)
        try:
            decoded = base64.b64decode(value[:100])  # Check first 100 chars
            # Common image file headers
            if decoded.startswith((b'\xff\xd8\xff', b'\x89PNG', b'GIF8', b'RIFF')):
                return True
        except:
            pass
        
        return False

    def _mask_data(self, data):
        if isinstance(data, dict):
            masked_data = {}
            for key, value in data.items():
                key_lower = key.lower()
                if key_lower in self._hidden_keys:
                    if self._is_base64_image(str(value)):
                        masked_data[key] = 'base64 encoded images are too big to process'
                    else:
                        masked_data[key] = '*' * len(str(value))
                else:
                    masked_data[key] = self._mask_data(value)
            return masked_data

        elif isinstance(data, list):
            return [self._mask_data(item) for item in data]

        return data

    def _mask_auth_header(self, auth_header):
        if ' ' not in auth_header:
            return '*'*len(auth_header)  # likely malformed, just mask the entire header

        auth_scheme, auth_value = auth_header.split(' ', maxsplit=1)
        if auth_scheme in self.COMMON_AUTH_SCHEMES:
            return f'{auth_scheme} {"*"*len(auth_value)}'

        return '*'*len(auth_header)

    def handle_request(self):
        if self._disabled:
            return

        payload = deepcopy(self._payload_template)

        # Keep the Flask software identifier we set in template
        pass

        request_headers = dict(request.headers)
        
        # Mask sensitive headers
        for header_name in list(request_headers.keys()):
            if header_name.lower() in self.SENSITIVE_HEADERS:
                if header_name.lower() == 'authorization' and self._should_mask_auth_header:
                    request_headers[header_name] = self._mask_auth_header(request_headers[header_name])
                else:
                    request_headers[header_name] = '*' * len(request_headers[header_name])
        
        # Apply general masking
        request_headers = self._mask_data(request_headers)

        x_forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        request_ip = x_forwarded_for or request.remote_addr or 'bogon'
        
        # Extract first valid IPv4 address if multiple IPs are present
        if request_ip and ',' in request_ip:
            ips = [ip.strip() for ip in request_ip.split(',')]
            for ip in ips:
                # Simple IPv4 validation
                if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
                    request_ip = ip
                    break
            else:
                request_ip = 'bogon'
        elif not request_ip or not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', request_ip or ''):
            request_ip = 'bogon'

        # Get route path - try to get the actual route pattern
        route_path = None
        try:
            if hasattr(request, 'endpoint') and request.endpoint:
                from flask import current_app
                for rule in current_app.url_map.iter_rules():
                    if rule.endpoint == request.endpoint:
                        route_path = rule.rule
                        break
        except:
            pass
        
        # If we couldn't determine the parameterized route, omit it instead of null
        if not route_path or route_path == request.path:
            route_path = request.path  # Use actual path instead of null

        payload['data']['request'] = {
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            'method': request.method or 'GET',
            'url': request.url,
            'route_path': route_path,
            'user_agent': request.headers.get('User-Agent', ''),
            'headers': request_headers,
            'ip': request_ip,
            'query': self._mask_data(dict(request.args)),
            'body': {},
        }

        # if the client is acting maliciously, they can still exhaust the server memory by not providing a
        # content-length header or setting transfer-encoding header to chunked, this is a best-effort mitigation,
        # there should be other mechanisms in place to prevent this in production environments
        if (request.content_length or 0) < self._limit_request_body_size:
            if self._request_transformer:
                try:
                    request_body = self._request_transformer(request.get_data())
                    try:
                        dumps(request_body)
                    except JSONDecodeError:
                        raise ValueError('Request transformer must return a JSON serializable object')

                except Exception as e:
                    logger.error(f'Error in request transformer: {e.__class__.__name__}{e.args}')
                    last_frame = extract_tb(e.__traceback__)[-1]
                    payload['data']['errors'].append({
                        'source': 'onError',
                        'type': e.__class__.__name__,
                        'message': ', '.join(str(f) for f in e.args),
                        'file': last_frame.filename,
                        'line': last_frame.lineno
                    })
                    request_body = {}

            else:
                try:
                    request_body = loads(request.get_data().decode('utf-8', 'replace'))
                except JSONDecodeError:
                    request_body = {}

            payload['data']['request']['body'] = self._mask_data(request_body) if request_body else {}

        g.treblle_payload = payload
        g.treblle_start_time = time()

    def handle_response(self, response):
        if self._disabled:
            return response

        response_headers = dict(response.headers)
        
        # Mask sensitive headers in response
        for header_name in list(response_headers.keys()):
            if header_name.lower() in self.SENSITIVE_HEADERS:
                response_headers[header_name] = '*' * len(response_headers[header_name])
        
        # Apply general masking
        response_headers = self._mask_data(response_headers)

        payload = g.treblle_payload
        payload['data']['response'] = {
            'code': response.status_code or 200,
            'headers': response_headers,
            'load_time': int((time()-g.treblle_start_time) * 1000),
        }

        if isinstance(response.response, GeneratorType):
            # streaming response - we don't want to block the request thread to wait for the response to finish
            # or load the entire response into memory
            payload['data']['response'].update({'size': 0, 'body': {}})
        else:
            if self._response_transformer:
                # Check if response body exceeds 2MB limit before transformation
                if len(response.data) > self.MAX_RESPONSE_BODY_SIZE:
                    payload['data']['errors'].append({
                        'source': 'onError',
                        'type': 'E_USER_ERROR',
                        'message': 'JSON response size is over 2MB',
                        'file': '',
                        'line': 0
                    })
                    response_body = {}
                    response_size = 0
                else:
                    try:
                        response_body = self._response_transformer(response.data)
                        try:
                            dumps(response_body)
                        except JSONDecodeError:
                            raise ValueError('Response transformer must return a JSON serializable object')

                    except Exception as e:
                        logger.error(f'Error in response transformer: {e.__class__.__name__}{e.args}')
                        last_frame = extract_tb(e.__traceback__)[-1]
                        payload['data']['errors'].append({
                            'source': 'onError',
                            'type': e.__class__.__name__,
                            'message': ', '.join(str(f) for f in e.args),
                            'file': last_frame.filename,
                            'line': last_frame.lineno
                        })
                        response_body = {}
                    response_size = len(response.data)

            else:
                # Check if response body exceeds 2MB limit
                if len(response.data) > self.MAX_RESPONSE_BODY_SIZE:
                    payload['data']['errors'].append({
                        'source': 'onError',
                        'type': 'E_USER_ERROR',
                        'message': 'JSON response size is over 2MB',
                        'file': '',
                        'line': 0
                    })
                    response_body = {}
                    response_size = 0
                else:
                    try:
                        response_body = loads(response.data.decode('utf-8', 'replace'))
                    except (JSONDecodeError, UnicodeDecodeError):
                        response_body = {}
                    response_size = len(response.data)

            payload['data']['response']['body'] = self._mask_data(response_body) if response_body else {}
            payload['data']['response']['size'] = response_size

        return response

    def finalize(self, exception):
        if self._disabled or not hasattr(g, 'treblle_payload'):
            return

        # Add root level timestamp and request ID
        g.treblle_payload['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        g.treblle_payload['request_id'] = str(uuid4())

        if exception:
            # treblle doesn't support entire traceback, we'll only send the last frame
            last_frame = extract_tb(exception.__traceback__)[-1]

            g.treblle_payload['data']['errors'].append({
                'source': 'onError',
                'type': exception.__class__.__name__,
                'message': ', '.join(str(f) for f in exception.args),
                'file': last_frame.filename,
                'line': last_frame.lineno
            })

        return g.treblle_payload
