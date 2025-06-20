from qka.core.data import data, set_source, get_source, register_data_source, get_available_sources
from qka.core.backtest import backtest
from qka.core.config import config, load_config
from qka.core.events import event_engine, emit_event, start_event_engine, stop_event_engine
from qka.brokers.trade import create_trader
from qka.brokers.client import QMTClient
from qka.brokers.server import QMTServer

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version("qka")
except PackageNotFoundError:
    __version__ = "0.1.0"  # fallback version

__all__ = [
    'data', 'set_source', 'get_source', 'register_data_source', 'get_available_sources',
    'backtest', 'config', 'load_config',
    'event_engine', 'emit_event', 'start_event_engine', 'stop_event_engine',
    'create_trader', 'QMTClient', 'QMTServer'
]