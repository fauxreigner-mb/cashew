#!/usr/bin/env python3
"""
Tests for cashew init wizard functionality
"""

import pytest
import tempfile
import yaml
import sqlite3
import subprocess
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the init functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cashew_init import (
    build_config, 
    create_database_schema, 
    write_config_file,
    detect_scheduling_backends,
    generate_cron_entries,
    install_system_crontab,
    setup_scheduling
)


class TestInitWizard:
    """Test the init wizard functionality"""
    
    def test_build_config_non_interactive_defaults(self, tmp_path):
        """Test that non-interactive mode generates valid config with defaults"""
        config_path = tmp_path / "config.yaml"
        data_dir = str(tmp_path / "data")
        
        config, db_path, api_key, resulting_data_dir = build_config(
            interactive=False,
            config_path=str(config_path),
            data_dir_override=data_dir
        )
        
        # Check that config contains required sections
        assert 'database' in config
        assert 'models' in config
        assert 'domains' in config
        assert 'sleep' in config
        assert 'performance' in config
        
        # Check sleep configuration
        sleep_config = config['sleep']
        assert 'enabled' in sleep_config
        assert 'schedule' in sleep_config
        assert 'frequency' in sleep_config
        assert sleep_config['frequency'] == '6h'  # default
        
        # Check paths
        assert db_path == str(Path(data_dir) / "graph.db")
        assert resulting_data_dir == data_dir
        
    def test_create_database_schema(self, tmp_path):
        """Test that database schema creation works"""
        db_path = tmp_path / "test.db"
        create_database_schema(str(db_path))
        
        # Check that database was created and has correct tables
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['thought_nodes', 'derivation_edges', 'embeddings', 'hotspots', 'metrics']
        for table in expected_tables:
            assert table in tables
        
        conn.close()
        
    def test_config_file_write_and_read(self, tmp_path):
        """Test config file writing and reading"""
        config_path = tmp_path / "config.yaml"
        
        test_config = {
            'database': {'path': 'data/graph.db'},
            'sleep': {'frequency': '12h', 'enabled': True}
        }
        
        write_config_file(test_config, str(config_path))
        
        # Verify file was written correctly
        assert config_path.exists()
        
        with open(config_path, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        assert loaded_config['database']['path'] == 'data/graph.db'
        assert loaded_config['sleep']['frequency'] == '12h'


class TestSchedulingSetup:
    """Test the scheduling functionality"""
    
    def test_detect_scheduling_backends(self):
        """Test scheduling backend detection"""
        backends = detect_scheduling_backends()
        
        assert 'crontab' in backends
        assert 'openclaw' in backends  
        assert 'manual' in backends
        assert backends['manual'] is True  # manual is always available
        
        # crontab should be available if the command exists
        import shutil
        expected_crontab = shutil.which('crontab') is not None
        assert backends['crontab'] == expected_crontab
        
    def test_generate_cron_entries_6h(self, tmp_path):
        """Test cron entry generation for 6 hour frequency"""
        config_path = tmp_path / "config.yaml"
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        entries = generate_cron_entries(str(config_path), str(data_dir), "6h")
        
        assert len(entries) == 2  # sleep and think
        
        # Check that entries contain required elements
        sleep_entry = entries[0]
        think_entry = entries[1]
        
        # Should use */6 for 6 hour frequency
        assert "*/6" in sleep_entry
        assert "*/6" in think_entry
        
        # Should contain full config path
        assert str(config_path.resolve()) in sleep_entry
        assert str(config_path.resolve()) in think_entry
        
        # Should set CASHEW_CONFIG_PATH
        assert "CASHEW_CONFIG_PATH=" in sleep_entry
        assert "CASHEW_CONFIG_PATH=" in think_entry
        
        # Should contain log redirection
        assert "sleep.log" in sleep_entry
        assert "think.log" in think_entry
        
    def test_generate_cron_entries_12h(self, tmp_path):
        """Test cron entry generation for 12 hour frequency"""
        config_path = tmp_path / "config.yaml"
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        entries = generate_cron_entries(str(config_path), str(data_dir), "12h")
        
        # Should use */12 for 12 hour frequency
        assert any("*/12" in entry for entry in entries)
        
    def test_generate_cron_entries_manual(self, tmp_path):
        """Test cron entry generation for manual frequency"""
        config_path = tmp_path / "config.yaml"
        data_dir = tmp_path / "data"
        
        entries = generate_cron_entries(str(config_path), str(data_dir), "manual")
        
        # Manual should return empty list
        assert len(entries) == 0
        
    def test_cron_setup_generates_valid_entries(self, tmp_path):
        """Init must generate valid cron entries that use the correct config path"""
        config_path = tmp_path / "config.yaml"
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Build config with non-interactive mode
        config, db_path, api_key, resulting_data_dir = build_config(
            interactive=False,
            config_path=str(config_path),
            data_dir_override=str(data_dir)
        )
        
        # Write config file
        write_config_file(config, str(config_path))
        
        # Create database
        create_database_schema(db_path)
        
        # Test cron entry generation (dry run mode to avoid installing)
        entries = generate_cron_entries(str(config_path), str(data_dir), "6h")
        
        # Verify entries are valid
        assert len(entries) == 2
        
        for entry in entries:
            # Must have 5 cron time fields followed by command
            parts = entry.split()
            assert len(parts) >= 6
            
            # First 5 parts should be cron time specification
            time_spec = ' '.join(parts[:5])
            assert "*/6" in time_spec
            
            # Command part should contain CASHEW_CONFIG_PATH
            command = ' '.join(parts[5:])
            assert "CASHEW_CONFIG_PATH=" in command
            assert str(config_path.resolve()) in command
            
            # Should use absolute paths (no relative paths in cron)
            assert str(Path(__file__).parent.parent.resolve()) in command
            
    @patch('subprocess.run')
    def test_install_system_crontab_dry_run(self, mock_run, tmp_path):
        """Test crontab installation in dry run mode"""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        
        entries = ["0 */6 * * * /usr/bin/test"]
        
        # Dry run should not actually call crontab
        result = install_system_crontab(entries, dry_run=True)
        
        assert result is True
        # Should not have called crontab in dry run
        mock_run.assert_not_called()
        
    @patch('subprocess.run')
    def test_install_system_crontab_avoids_duplicates(self, mock_run, tmp_path):
        """Test that installing crontab twice doesn't create duplicates"""
        # Mock existing crontab with cashew entries
        existing_crontab = "# Some existing entry\n0 */6 * * * old-command  # cashew\n"
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=existing_crontab),  # crontab -l
            MagicMock(returncode=0, stdout="")  # crontab -
        ]
        
        entries = ["0 */6 * * * new-command"]
        result = install_system_crontab(entries, dry_run=False)
        
        assert result is True
        assert mock_run.call_count == 2
        
        # Check that the new crontab doesn't have old cashew entries
        install_call = mock_run.call_args_list[1]
        new_crontab = install_call[1]['input']  # keyword argument 'input'
        
        # Should not contain the old command
        assert "old-command" not in new_crontab
        # Should contain the new command
        assert "new-command" in new_crontab
        # Should have cashew marker
        assert "# cashew" in new_crontab
        
    def test_setup_scheduling_manual_mode(self, tmp_path):
        """Test scheduling setup in manual mode"""
        config = {
            'sleep': {
                'frequency': 'manual',
                'enabled': False
            }
        }
        
        result = setup_scheduling(
            config, 
            str(tmp_path / "config.yaml"), 
            str(tmp_path / "data"),
            interactive=False,
            dry_run=True
        )
        
        assert result is True
        
    @patch('cashew_init.detect_scheduling_backends')
    def test_setup_scheduling_non_interactive_auto_detect(self, mock_detect, tmp_path):
        """Test scheduling setup auto-detects best backend in non-interactive mode"""
        # Mock backend detection to prefer OpenClaw
        mock_detect.return_value = {
            'crontab': True,
            'openclaw': True,
            'manual': True
        }
        
        config = {
            'sleep': {
                'frequency': '6h',
                'enabled': True
            }
        }
        
        with patch('cashew_init.setup_openclaw_cron', return_value=True) as mock_openclaw:
            result = setup_scheduling(
                config,
                str(tmp_path / "config.yaml"),
                str(tmp_path / "data"), 
                interactive=False,
                dry_run=True
            )
            
            assert result is True
            mock_openclaw.assert_called_once()


class TestFullInitFlow:
    """Test the complete init flow"""
    
    def test_init_creates_working_setup(self, tmp_path):
        """Test that full init creates a working cashew setup"""
        config_path = tmp_path / "config.yaml"
        data_dir = tmp_path / "data"
        
        # Run full config build
        config, db_path, api_key, resulting_data_dir = build_config(
            interactive=False,
            config_path=str(config_path),
            data_dir_override=str(data_dir)
        )
        
        # Create directories and database
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "logs").mkdir(exist_ok=True)
        (data_dir / "backups").mkdir(exist_ok=True)
        (data_dir / "models").mkdir(exist_ok=True)
        
        create_database_schema(db_path)
        write_config_file(config, str(config_path))
        
        # Verify everything was created correctly
        assert config_path.exists()
        assert Path(db_path).exists()
        assert (data_dir / "logs").exists()
        assert (data_dir / "backups").exists()
        assert (data_dir / "models").exists()
        
        # Verify config contains expected values
        with open(config_path, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        assert loaded_config['sleep']['frequency'] == '6h'
        assert loaded_config['models']['embedding']['provider'] == 'sentence-transformers'
        
        # Test database connectivity
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        assert table_count >= 4  # Should have core tables
        conn.close()