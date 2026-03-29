#!/bin/bash
cd /home/jonia/.openclaw/workspace
export $(grep -v "^#" secrets/.env | xargs)
python3 scripts/health_webhook.py --serve
