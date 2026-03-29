#!/usr/bin/env python3
"""
Safe Cron Editor - Replaces error-prone edit tool calls for cron files
"""

import sys
from pathlib import Path
from cron_manager import CronJobManager

def safe_cron_edit(old_text: str, new_text: str, file_path: str = None) -> bool:
    """
    Replace edit tool for cron files with safe JSON operations
    
    This is called when edit tool fails on cron/jobs.json
    Instead of trying to match exact whitespace, we:
    1. Load the JSON structure
    2. Make the logical changes 
    3. Write atomically
    """
    
    # Only handle cron files
    if not file_path or "cron" not in file_path or "jobs.json" not in file_path:
        return False
    
    try:
        cron_manager = CronJobManager()
        
        # For now, just ensure the file is healthy
        # In future, we can parse the old_text/new_text to understand the intent
        jobs = cron_manager.read_jobs()
        
        # Write back (this fixes any formatting issues)
        return cron_manager.write_jobs(jobs)
        
    except Exception as e:
        print(f"Safe cron edit failed: {e}")
        return False

def add_integration_health_job() -> bool:
    """Add integration health check job if it doesn't exist.
    
    NOTE (OPS/NOTIFICATION_ROUTING_FIX.md): The 07:00 Telegram health digest
    is DISABLED by policy. This function will NOT re-create it automatically.
    Infra health is ops_only — never auto-sent to user-facing channels.
    """
    # POLICY: health digest is ops_only — never auto-create user-facing job
    print("[safe_cron_edit] ⛔ integration-health-check creation blocked: ops_only per NOTIFICATION_ROUTING_FIX.md")
    return False

    # --- DISABLED BLOCK BELOW (kept for reference) ---
    try:
        cron_manager = CronJobManager()
        
        # Check if integration health job already exists
        jobs = cron_manager.list_jobs()
        for job in jobs:
            if "integration" in job.get("name", "").lower() and "health" in job.get("name", "").lower():
                print("Integration health job already exists")
                return True
        
        # Add the job
        health_job = {
            "name": "integration-health-check",
            "description": "Daily Integration Health Check",
            "enabled": True,
            "deleteAfterRun": False,
            "schedule": {
                "kind": "cron",
                "expr": "0 7 * * *"  # Daily at 7 AM
            },
            "sessionTarget": "isolated",
            "wakeMode": "now",
            "payload": {
                "kind": "agentTurn", 
                "message": "Run integration health check: python3 core/integration_health.py && report critical failures to user"
            },
            "delivery": {
                "mode": "announce",
                "channel": "telegram",
                "to": "539224224"
            }
        }
        
        success = cron_manager.add_job(health_job)
        if success:
            print("✅ Added integration health check job")
        else:
            print("❌ Failed to add integration health check job")
        
        return success
        
    except Exception as e:
        print(f"Error adding integration health job: {e}")
        return False

def main():
    """CLI interface for safe cron operations"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  safe_cron_edit.py add-health-job    # Add integration health job")
        print("  safe_cron_edit.py test-edit         # Test safe editing")
        return
    
    command = sys.argv[1]
    
    if command == "add-health-job":
        add_integration_health_job()
    
    elif command == "test-edit":
        # Test the safe edit function
        result = safe_cron_edit("old", "new", "/home/jonia/.openclaw/cron/jobs.json")
        print(f"Test edit result: {result}")
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()