"""
Configuration Manager Module

Provides centralized configuration management for the X10 Think application.
Handles loading, saving, and validating configuration settings from YAML files.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Configuration for a specific engine."""
    
    enabled: bool = True
    """Whether this engine is active."""
    
    parameters: Dict[str, Any] = field(default_factory=dict)
    """Engine-specific parameters."""
    
    strict_mode: bool = False
    """If True, engine will raise errors on rule violations."""


@dataclass
class AppConfig:
    """Main application configuration structure."""
    
    # Application settings
    app_name: str = "X10 Think MIDI Intelligence Engine"
    version: str = "1.0.0"
    debug_mode: bool = False
    
    # Paths
    project_directory: str = ""
    midi_input_directory: str = ""
    midi_output_directory: str = ""
    database_path: str = ""
    log_directory: str = ""
    
    # Engine configurations
    parser_engine: EngineConfig = field(default_factory=EngineConfig)
    track_intelligence_engine: EngineConfig = field(default_factory=EngineConfig)
    rx_engine: EngineConfig = field(default_factory=EngineConfig)
    humanization_engine: EngineConfig = field(default_factory=EngineConfig)
    harmony_engine: EngineConfig = field(default_factory=EngineConfig)
    expression_engine: EngineConfig = field(default_factory=EngineConfig)
    velocity_engine: EngineConfig = field(default_factory=EngineConfig)
    musical_rules_engine: EngineConfig = field(default_factory=EngineConfig)
    
    # GUI settings
    theme: str = "dark"
    language: str = "en"
    window_width: int = 1400
    window_height: int = 900
    
    # Export settings
    export_format: str = "mid"
    preserve_original: bool = True
    add_metadata: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_max_size_mb: int = 10
    log_backup_count: int = 5
    
    # Database
    db_auto_backup: bool = True
    db_backup_interval_days: int = 7


class ConfigManager:
    """
    Centralized configuration manager for the X10 Think application.
    
    This class handles loading, saving, and managing application configuration
    from YAML files. It provides type-safe access to configuration values
    and supports hot-reloading of configuration changes.
    
    Example:
        >>> config = ConfigManager()
        >>> config.load("config.yaml")
        >>> print(config.app_config.debug_mode)
        >>> config.save("config.yaml")
    """
    
    DEFAULT_CONFIG_FILE = "config.yaml"
    
    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to the configuration file.
        """
        self._config_path: Optional[Path] = config_path
        self._app_config: AppConfig = AppConfig()
        self._raw_config: Dict[str, Any] = {}
        logger.debug("ConfigManager initialized")
    
    @property
    def app_config(self) -> AppConfig:
        """Get the current application configuration."""
        return self._app_config
    
    @property
    def config_path(self) -> Optional[Path]:
        """Get the current configuration file path."""
        return self._config_path
    
    def load(self, config_path: Optional[Path] = None) -> bool:
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to the configuration file. If None, uses the
                        previously set path or default.
        
        Returns:
            True if configuration was loaded successfully, False otherwise.
        """
        path = config_path or self._config_path or Path(self.DEFAULT_CONFIG_FILE)
        
        if not path.exists():
            logger.info(f"Configuration file not found: {path}, using defaults")
            self._config_path = path
            return True
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._raw_config = yaml.safe_load(f) or {}
            
            self._apply_config(self._raw_config)
            self._config_path = path
            logger.info(f"Configuration loaded from: {path}")
            return True
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def save(self, config_path: Optional[Path] = None) -> bool:
        """
        Save current configuration to a YAML file.
        
        Args:
            config_path: Path to save the configuration file. If None, uses
                        the previously set path.
        
        Returns:
            True if configuration was saved successfully, False otherwise.
        """
        path = config_path or self._config_path
        
        if path is None:
            logger.error("No configuration path specified")
            return False
        
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            
            config_dict = self._to_dict()
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Configuration saved to: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def reset_to_defaults(self) -> None:
        """Reset all configuration values to their defaults."""
        self._app_config = AppConfig()
        self._raw_config = {}
        logger.info("Configuration reset to defaults")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-notation key.
        
        Args:
            key: Dot-separated key path (e.g., "parser_engine.enabled").
            default: Default value if key doesn't exist.
        
        Returns:
            The configuration value or default.
        """
        keys = key.split('.')
        value = self._raw_config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set a configuration value by dot-notation key.
        
        Args:
            key: Dot-separated key path (e.g., "parser_engine.enabled").
            value: Value to set.
        
        Returns:
            True if successful, False otherwise.
        """
        keys = key.split('.')
        config = self._raw_config
        
        try:
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            self._apply_config(self._raw_config)
            return True
        except Exception as e:
            logger.error(f"Error setting configuration value: {e}")
            return False
    
    def _apply_config(self, raw: Dict[str, Any]) -> None:
        """Apply raw configuration dictionary to AppConfig object."""
        # Basic fields
        for field_name in ['app_name', 'version', 'debug_mode', 'theme', 
                          'language', 'window_width', 'window_height',
                          'export_format', 'preserve_original', 'add_metadata',
                          'log_level', 'log_to_file', 'log_max_size_mb',
                          'log_backup_count', 'db_auto_backup', 
                          'db_backup_interval_days']:
            if field_name in raw:
                setattr(self._app_config, field_name, raw[field_name])
        
        # Path fields
        for field_name in ['project_directory', 'midi_input_directory', 
                          'midi_output_directory', 'database_path', 'log_directory']:
            if field_name in raw:
                setattr(self._app_config, field_name, raw[field_name])
        
        # Engine configurations
        engine_fields = ['parser_engine', 'track_intelligence_engine', 'rx_engine',
                        'humanization_engine', 'harmony_engine', 'expression_engine',
                        'velocity_engine', 'musical_rules_engine']
        
        for field_name in engine_fields:
            if field_name in raw:
                engine_data = raw[field_name]
                engine_config = EngineConfig(
                    enabled=engine_data.get('enabled', True),
                    parameters=engine_data.get('parameters', {}),
                    strict_mode=engine_data.get('strict_mode', False)
                )
                setattr(self._app_config, field_name, engine_config)
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert AppConfig to dictionary for serialization."""
        config = asdict(self._app_config)
        
        # Convert engine configs to proper format
        for field_name in ['parser_engine', 'track_intelligence_engine', 'rx_engine',
                          'humanization_engine', 'harmony_engine', 'expression_engine',
                          'velocity_engine', 'musical_rules_engine']:
            engine_config = getattr(self._app_config, field_name)
            config[field_name] = {
                'enabled': engine_config.enabled,
                'parameters': engine_config.parameters,
                'strict_mode': engine_config.strict_mode
            }
        
        return config
    
    def validate(self) -> List[str]:
        """
        Validate the current configuration.
        
        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []
        
        # Validate paths
        for path_field in ['project_directory', 'midi_input_directory', 
                          'midi_output_directory', 'database_path', 'log_directory']:
            path_value = getattr(self._app_config, path_field)
            if path_value and not Path(path_value).parent.exists():
                errors.append(f"Invalid path for {path_field}: parent directory does not exist")
        
        # Validate numeric ranges
        if self._app_config.window_width < 800:
            errors.append("window_width must be at least 800")
        if self._app_config.window_height < 600:
            errors.append("window_height must be at least 600")
        
        # Validate log settings
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self._app_config.log_level not in valid_log_levels:
            errors.append(f"Invalid log_level: must be one of {valid_log_levels}")
        
        return errors
