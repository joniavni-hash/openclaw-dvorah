#!/usr/bin/env python3
"""
Agent Registry - OpenClaw Agent Management (Fixed)
מנהל את כל הagents הזמינים ומחבר אותם לorchestrator
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

class AgentRegistry:
    """מנהל רישום וביצוע agents"""
    
    def __init__(self):
        self.agents = {
            'tali': {
                'name': 'טלי - Marketing Agent',
                'domain': 'marketing',
                'skills': ['larry-marketing', 'social-media', 'content-creation'],
                'script': 'agents/tali/tali_agent.py',
                'description': 'מומחית שיווק דיגיטלי - TikTok, Instagram, פרסום'
            },
            'masha': {
                'name': 'מאשה - Legal Agent', 
                'domain': 'legal',
                'skills': ['contract-review', 'legal-analysis'],
                'script': 'agents/masha/masha_agent.py',
                'description': 'יועצת משפטית - חוזים, ניתוח משפטי, סיכונים'
            },
            'dana': {
                'name': 'דנה - Fitness Agent',
                'domain': 'fitness', 
                'skills': ['fitness-tracking', 'nutrition', 'health'],
                'script': 'agents/dana-fitness/dana_agent.py',
                'description': 'מאמנת כושר - מעקב תזונה, יעדים, תכנון אימונים'
            },
            'tzofit': {
                'name': 'צופית - Research Agent',
                'domain': 'research',
                'skills': ['research', 'analysis', 'intelligence', 'competition'],
                'script': 'agents/tzofit-research/tzofit_agent.py', 
                'description': 'חוקרת - מחקר שוק, תחרותי, מודיעין עסקי'
            },
            'odya': {
                'name': 'אודיה - WhatsApp Agent',
                'domain': 'groups',
                'skills': ['whatsapp-groups', 'communication', 'summarization'],
                'script': 'agents/odya-whatsapp/odya_agent.py',
                'description': 'מתאמת קבוצות WhatsApp - סיכומים, תקשורת'
            },

            'gabi': {
                'name': 'גבי - CTO Agent',
                'domain': 'cto',
                'skills': ['system-health', 'updates', 'self-improvement', 'error-analysis'],
                'script': 'agents/gabi-cto/gabi_agent.py',
                'description': 'CTO מערכת - בריאות, עדכונים, שיפור עצמי, אבחון שגיאות'
            }
        }
    
    def get_available_agents(self) -> Dict[str, Any]:
        """החזר רשימת agents זמינים"""
        return self.agents
    
    def execute_agent(self, agent_id: str, task: str, context: Dict = None) -> Dict[str, Any]:
        """הפעל agent ספציפי"""
        if agent_id not in self.agents:
            return {'status': 'error', 'message': f'Agent {agent_id} not found'}
        
        agent_info = self.agents[agent_id]
        script_path = Path(agent_info['script'])
        
        # בנה את הcommand
        cmd = ['python3', str(script_path), '--task', task]
        if context:
            cmd.extend(['--context', json.dumps(context)])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd='/home/jonia/.openclaw/workspace'
            )
            
            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout)
                    return {
                        'status': 'success',
                        'agent': agent_id,
                        'result': output
                    }
                except json.JSONDecodeError:
                    return {
                        'status': 'success', 
                        'agent': agent_id,
                        'result': {'output': result.stdout}
                    }
            else:
                return {
                    'status': 'error',
                    'agent': agent_id,
                    'error': result.stderr,
                    'output': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'agent': agent_id,
                'message': 'Agent execution timed out'
            }
        except Exception as e:
            return {
                'status': 'error',
                'agent': agent_id,
                'error': str(e)
            }
    
    def test_agent(self, agent_id: str) -> Dict[str, Any]:
        """בדוק זמינות agent"""
        if agent_id not in self.agents:
            return {'available': False, 'reason': 'Agent not found'}
            
        script_path = Path(self.agents[agent_id]['script'])
        if not script_path.exists():
            return {'available': False, 'reason': f'Script not found: {script_path}'}
            
        try:
            result = subprocess.run(
                ['python3', str(script_path), '--test'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd='/home/jonia/.openclaw/workspace'
            )
            return {
                'available': True if result.returncode == 0 else False,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {'available': False, 'reason': str(e)}

# Global registry instance
registry = AgentRegistry()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true', help='List all agents')
    parser.add_argument('--test', type=str, help='Test specific agent')
    parser.add_argument('--execute', type=str, help='Execute agent')
    parser.add_argument('--task', type=str, help='Task for agent')
    
    args = parser.parse_args()
    
    if args.list:
        agents = registry.get_available_agents()
        print("🤖 Available Agents:")
        for agent_id, info in agents.items():
            print(f"- {agent_id}: {info['description']}")
            
    elif args.test:
        result = registry.test_agent(args.test)
        print(f"🧪 Agent {args.test} test:", json.dumps(result, indent=2))
        
    elif args.execute and args.task:
        result = registry.execute_agent(args.execute, args.task)
        print(json.dumps(result, indent=2))