from abc import ABC, abstractmethod
from qka.core.broker import Broker

class Strategy(ABC):
    def __init__(self):
        self.broker = Broker()
    
    @abstractmethod
    def on_bar(self):
        pass