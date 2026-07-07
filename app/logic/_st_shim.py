"""
Drop-in replacement for the small subset of the Streamlit API used inside
dcf_engine.py's calculation functions (WACC, DCF, beta, comparative
valuation, etc). Those functions were written for Streamlit but only use
`st.*` for informational side-effects (info/warning/error/success/write/
caption/markdown/expander) plus `st.session_state` and `st.cache_data`
for rate-limit bookkeeping — none of it affects a function's return
value. Rather than hand-editing hundreds of scattered calls across a
5,000+ line file, this shim absorbs them all: messages go to Python
logging (visible in server logs / captured per-request if needed),
`session_state` becomes a plain persistent dict, and `cache_data` is a
harmless passthrough decorator (real caching is handled separately via
Flask-Caching where it matters).

If a genuinely new interactive widget call shows up here in a future
copy-paste from the old app, it will raise AttributeError loudly rather
than silently doing the wrong thing — that's intentional.
"""
import logging
from contextlib import contextmanager

logger = logging.getLogger("dcf_engine")


class _SessionState(dict):
    """Lets old code keep doing st.session_state.foo = bar / st.session_state.get(...)."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


class _StreamlitShim:
    def __init__(self):
        self.session_state = _SessionState()

    # --- display calls -> logging (no-op for the caller's return value) ---
    def info(self, msg="", *a, **k):
        logger.info(str(msg))

    def warning(self, msg="", *a, **k):
        logger.warning(str(msg))

    def error(self, msg="", *a, **k):
        logger.error(str(msg))

    def success(self, msg="", *a, **k):
        logger.info("[OK] %s", msg)

    def write(self, *args, **k):
        logger.debug(" ".join(str(a) for a in args))

    def caption(self, msg="", *a, **k):
        logger.debug(str(msg))

    def markdown(self, msg="", *a, **k):
        logger.debug(str(msg))

    def code(self, msg="", *a, **k):
        logger.debug(str(msg))

    def json(self, obj, *a, **k):
        logger.debug(str(obj))

    def latex(self, *a, **k):
        pass

    def toast(self, *a, **k):
        pass

    # --- layout/interactive no-ops that occasionally sneak in ---
    @contextmanager
    def expander(self, *a, **k):
        yield self

    def set_page_config(self, *a, **k):
        pass

    # --- caching: real caching happens in Flask-Caching where it matters;
    # here it's a harmless passthrough so decorated functions still work.
    def cache_data(self, *dargs, **dkwargs):
        def decorator(func):
            return func
        # Support both @st.cache_data and @st.cache_data(ttl=...)
        if dargs and callable(dargs[0]):
            return dargs[0]
        return decorator


st = _StreamlitShim()
