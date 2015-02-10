"""Models for the util app. """
import cStringIO
import gzip

from django.db import models
from django.utils.text import compress_string

from config_models.models import ConfigurationModel


class RateLimitConfiguration(ConfigurationModel):
    """Configuration flag to enable/disable rate limiting.

    Applies to Django Rest Framework views.

    This is useful for disabling rate limiting for performance tests.
    When enabled, it will disable rate limiting on any view decorated
    with the `can_disable_rate_limit` class decorator.
    """
    pass


def uncompress_string(s):
    """helper function to reverse django.utils.text.compress_string"""

    try:
        val = s.encode('utf').decode('base64')
        zbuf = cStringIO.StringIO(val)
        zfile = gzip.GzipFile(fileobj=zbuf)
        ret = zfile.read()
        zfile.close()
    except:
        ret = s
    return ret


class CompressedTextField(models.TextField):
    """transparently compress data before hitting the db and uncompress after fetching"""

    def get_prep_value(self, value):
        if value is not None:
            if isinstance(value, unicode):
                value = value.encode('utf8')
            value = compress_string(value)
            value = value.encode('base64').decode('utf8')
        return value

    def _get_val_from_obj(self, obj):
        if obj:
            value = uncompress_string(getattr(obj, self.attname))
            if value is not None:
                try:
                    value = value.decode('utf8')
                except UnicodeDecodeError:
                    pass
                return value
            else:
                return self.get_default()
        else:
            return self.get_default()

    def south_field_triple(self):
        """Returns a suitable description of this field for South."""
        # We'll just introspect the _actual_ field.
        from south.modelsinspector import introspector

        field_class = "django.db.models.fields.TextField"
        args, kwargs = introspector(self)
        # That's our definition!
        return field_class, args, kwargs
