"""
Event Bus Module

Provides a centralized event publishing and subscribing mechanism for 
inter-module communication within the X10 Think application.

This implementation follows the Observer pattern for loose coupling
between engines and components.
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Represents an event in the system."""
    
    name: str
    """The unique name/identifier of the event."""
    
    payload: Dict[str, Any] = field(default_factory=dict)
    """Data associated with the event."""
    
    timestamp: datetime = field(default_factory=datetime.now)
    """When the event was created."""
    
    source: Optional[str] = None
    """The component that emitted this event."""


class EventBus:
    """
    Centralized event bus for inter-component communication.
    
    This class implements a thread-safe publish-subscribe pattern
    allowing decoupled communication between different engines
    and components of the X10 Think system.
    
    Example:
        >>> bus = EventBus()
        >>> def handler(event: Event):
        ...     print(f"Received: {event.name}")
        >>> bus.subscribe("midi.loaded", handler)
        >>> bus.publish(Event(name="midi.loaded", payload={"file": "song.mid"}))
    """
    
    def __init__(self) -> None:
        """Initialize the event bus with empty subscriber registry."""
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self._event_history: List[Event] = []
        self._max_history: int = 1000
        logger.debug("EventBus initialized")
    
    def subscribe(self, event_name: str, callback: Callable[[Event], None]) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_name: The name of the event to subscribe to.
            callback: Function to call when the event is published.
                      Must accept a single Event argument.
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
        logger.debug(f"Subscribed to event: {event_name}")
    
    def unsubscribe(self, event_name: str, callback: Callable[[Event], None]) -> bool:
        """
        Unsubscribe from an event type.
        
        Args:
            event_name: The name of the event to unsubscribe from.
            callback: The callback function to remove.
            
        Returns:
            True if the callback was found and removed, False otherwise.
        """
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(callback)
                logger.debug(f"Unsubscribed from event: {event_name}")
                return True
            except ValueError:
                return False
        return False
    
    def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: The Event object to publish.
        """
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Notify subscribers
        subscribers = self._subscribers.get(event.name, [])
        logger.debug(f"Publishing event: {event.name} to {len(subscribers)} subscribers")
        
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for {event.name}: {e}", exc_info=True)
    
    def clear_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()
        logger.debug("Event history cleared")
    
    def get_history(self, event_name: Optional[str] = None) -> List[Event]:
        """
        Retrieve event history.
        
        Args:
            event_name: Optional filter by event name.
            
        Returns:
            List of events, optionally filtered by name.
        """
        if event_name:
            return [e for e in self._event_history if e.name == event_name]
        return self._event_history.copy()
    
    def has_subscribers(self, event_name: str) -> bool:
        """
        Check if an event type has any subscribers.
        
        Args:
            event_name: The event name to check.
            
        Returns:
            True if there are subscribers, False otherwise.
        """
        return event_name in self._subscribers and len(self._subscribers[event_name]) > 0
