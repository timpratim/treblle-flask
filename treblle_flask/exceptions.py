# coding=utf-8

"""
treblle_flask.exceptions
~~~~~~~~~~~~~~~~~~~~~~~

This module implements Treblle-specific exceptions.
"""


class TreblleException(Exception):
    """Base exception class for Treblle-related errors."""
    
    @staticmethod
    def missing_api_key():
        return TreblleException(
            'No Api Key configured for Treblle. Ensure this is set in your .env before trying again.'
        )
    
    @staticmethod
    def missing_project_id():
        return TreblleException(
            'No Project Id configured for Treblle. Ensure this is set in your .env before trying again.'
        )
