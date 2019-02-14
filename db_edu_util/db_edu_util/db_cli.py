"""
Helper functions for using the Databricks CLI.
"""
from __future__ import annotations # PEP 563 (allows annotation forward refs)

import sys
import re
import json
from io import StringIO
from databricks_cli.cli import cli
from typing import Optional, Sequence

__all__ = ['databricks', 'DatabricksCliError']

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------

class DatabricksCliError(Exception):
    """
    Thrown to indicate errors with the databricks_cli invocation.
    """
    def __init__(self,
                 code: Optional[str] = None,
                 message: Optional[str] = None):
        super(Exception, self).__init__(message)
        self.code = code
        self.message = message

# -----------------------------------------------------------------------------
# Public Functions
# -----------------------------------------------------------------------------

def databricks(args: Sequence[str],
               db_profile: Optional[str] = None,
               capture_stdout: bool = False,
               verbose: bool = False):
    """
    Configure and run the Databricks CLI. Example of use:

    databricks(('workspace', 'ls', '/Users/foo@example.com'), db_profile='DEFAULT')

    :param args:           the "databricks" subcommand and arguments, as a list
                           or tuple
    :param capture_stdout: True to capture and return standard output. False
                           otherwise.
    :param db_profile:     The --profile argument for the "databricks" command,
                           if any; None otherwise.
    :param verbose:        True to emit verbose messages, False otherwise.

    :return: the string containing standard output, if capture_stdout is True.
             None otherwise.
    :raises DatabricksCliError: if the command fails. If possible, the code
            field will be set
    """
    if db_profile is None:
        db_profile = 'DEFAULT'

    kwargs = {
        'standalone_mode': False,
        'prog_name': 'databricks',
    }
    args = ('--profile', db_profile) + tuple(args)

    if verbose:
        print(f"+ databricks {' '.join(args)}")

    buf = None
    saved_stdout = None
    try:
        import unicodedata
        buf = StringIO()
        saved_stdout = sys.stdout
        sys.stdout = buf
        cli(args, **kwargs)
        output = buf.getvalue()
        if not capture_stdout:
            sys.stdout = saved_stdout
            saved_stdout = None
            print(output)
            output = None

        return output

    except:
        stdout = buf.getvalue()
        json_string = re.sub(r'^Error:\s+', '', stdout)
        default_msg = "Unknown error from databricks_cli"
        try:
            d = json.loads(json_string)
            code = d.get("error_code")
            msg = d.get("message", default_msg)
        except:
            code = None
            msg = stdout
        raise DatabricksCliError(code=code, message=msg)

    finally:
        if saved_stdout:
            sys.stdout = saved_stdout
