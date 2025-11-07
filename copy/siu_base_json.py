import base64
import datetime
import decimal
import json
import logging
import uuid
import types

from django.db import models
from django.forms.models import model_to_dict
from django.utils.duration import duration_iso_string
from django.utils.functional import Promise
from django.utils.timezone import is_aware
from requests import Response
from requests.adapters import CaseInsensitiveDict

logger = logging.getLogger(__name__)


class SiuJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types, and
    UUIDs.
    """

    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:19] + r[26:]
            if r.endswith("+00:00"):
                r = r[:-6] + "Z"
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.time):
            if is_aware(o):
                raise ValueError("JSON can't represent timezone-aware times.")
            r = o.isoformat()
            if o.microsecond:
                r = r[:12]
            return r
        elif isinstance(o, datetime.timedelta):
            return duration_iso_string(o)
        elif isinstance(o, (decimal.Decimal, uuid.UUID, Promise)):
            return str(o)
        elif isinstance(o, models.Model):
            r = model_to_dict(o)
            r["__module__"] = o.__module__
            r["__class__"] = o.__class__.__name__
            return r
        elif isinstance(o, Response):
            r = {
                "headers": o.headers,
                "status_code": o.status_code,
                "elapsed": o.elapsed,
                "url": o.url,
                "request": {
                    "method": o.request.method,
                    "headers": o.request.headers,
                    "url": o.request.url,
                    "body": o.request.body,
                },
            }
            if o.encoding:
                r.update(text=o.text)
            else:
                r.update(content_base64=base64.b64encode(o.content).decode("ascii"))
            if o.history:
                r["history"] = []
                for history_response in o.history:
                    r["history"].append(
                        {
                            "headers": history_response.headers,
                            "status_code": history_response.status_code,
                            "elapsed": history_response.elapsed,
                            "url": history_response.url,
                            "request": {
                                "method": history_response.request.method,
                                "headers": history_response.request.headers,
                                "url": history_response.request.url,
                                "body": history_response.request.body,
                            },
                        }
                    )
            return r
        elif isinstance(o, CaseInsensitiveDict):
            return dict(o)
        elif isinstance(o, bytes):
            return str(o)
        elif isinstance(o, BaseException):
            return str(o)
        elif isinstance(o, OSError):
            return str(o)
        elif isinstance(o, types.FunctionType):
            return str(o)
        elif isinstance(o, models.base.ModelBase):
            return str(o)
        else:
            t = type(o)
            logger.warning(f"unhandled type {t}")
            return super().default(o)
