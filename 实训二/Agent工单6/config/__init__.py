"""
配置管理模块
"""
import yaml
import os
from typing import Dict, Any
from pathlib import Path


class Config:
    """配置管理类"""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """加载配置文件"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            print(f"警告: 配置文件 {self.config_path} 不存在，使用默认配置")
            self._config = self._get_default_config()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'server': {
                'host': '0.0.0.0',
                'port': 8000,
                'debug': True
            },
            'database': {
                'type': 'sqlite',
                'sqlite': {
                    'path': './data/workorders.db'
                }
            },
            'ai': {
                'default_provider': 'anthropic'
            }
        }


# 全局配置实例
config = Config()
